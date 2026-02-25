"""MyBatis artifact generation agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from generation.artifacts.dao_generator import DAOGenerator
from generation.artifacts.dbio_generator import DBIOGenerator


def _camel_name(value: str) -> str:
    return "".join(part.capitalize() for part in value.split("_"))


def run_mybatis_generation(state: Dict[str, Any]) -> Dict[str, Any]:
    analysis_result = state.get("analysis_result") or {}
    output_dir = Path(state.get("output_dir", "output"))

    dto_dir = output_dir / "mybatis" / "dto"
    mapper_dir = output_dir / "mybatis" / "mapper"
    dto_dir.mkdir(parents=True, exist_ok=True)
    mapper_dir.mkdir(parents=True, exist_ok=True)

    sql_blocks = analysis_result.get("sql_blocks", [])
    errors = list(state.get("errors", []))

    dto_files: List[str] = []
    dao_files: List[str] = []
    xml_files: List[str] = []

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for block in sql_blocks:
        stem = Path(block.get("source_file", "unknown.pc")).stem
        grouped.setdefault(stem, []).append(block)

    for stem, calls in grouped.items():
        base_name = _camel_name(stem)
        dao_name = f"{base_name}Dao"

        # DTO placeholder
        dto_path = dto_dir / f"{base_name}Dto.java"
        dto_code = (
            "package com.example.mybatis.dto;\n\n"
            f"public class {base_name}Dto {{\n"
            "    // TODO: map host variables\n"
            "}\n"
        )
        dto_path.write_text(dto_code, encoding="utf-8")
        dto_files.append(str(dto_path))

        try:
            sql_calls = [
                {
                    "name": block.get("name", "sqlCall"),
                    "sql_type": block.get("sql_type", "select"),
                    "parsed_sql": block.get("sql", ""),
                    "input_vars": [],
                    "output_vars": [],
                }
                for block in calls
            ]
            id_to_path_map: Dict[str, str] = {}

            dao_generator = DAOGenerator(base_package="com.example.mybatis.mapper")
            dao_code = dao_generator.generate(sql_calls, id_to_path_map, dao_name)
            dao_path = mapper_dir / f"{dao_name}.java"
            dao_path.write_text(dao_code, encoding="utf-8")
            dao_files.append(str(dao_path))

            xml_generator = DBIOGenerator(base_package="com.example.mybatis.mapper")
            xml_code = xml_generator.generate(sql_calls, id_to_path_map, dao_name)
            xml_path = mapper_dir / f"{base_name}Mapper.xml"
            xml_path.write_text(xml_code, encoding="utf-8")
            xml_files.append(str(xml_path))
        except Exception as exc:
            errors.append(f"mybatis generation failed for {stem}: {exc}")

    return {
        "mybatis_result": {
            "dto_files": dto_files,
            "dao_files": dao_files,
            "xml_files": xml_files,
            "total_sqls": len(sql_blocks),
        },
        "errors": errors,
    }
