
import pytest
import tempfile
import os
import json
from infra.config.artifact_config import ArtifactConfig, ArtifactConfigLoader

class TestArtifactConfigLoader:
    def test_load_valid_file(self):
        """Test loading a valid JSONL config file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write('{"id": "source1", "base_package": "com.test.pkg", "dto_prefix": "Test"}\n')
            f.write('{"id": "source2", "base_package": "com.other.pkg"}\n')
            temp_path = f.name
            
        try:
            configs = ArtifactConfigLoader.load(temp_path)
            
            assert len(configs) == 2
            assert "source1" in configs
            assert "source2" in configs
            
            c1 = configs["source1"]
            assert c1.base_package == "com.test.pkg"
            assert c1.dto_prefix == "Test"
            assert c1.datasource == "MainDS" # default
            
            c2 = configs["source2"]
            assert c2.base_package == "com.other.pkg"
            assert c2.dto_prefix is None
            
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_get_config_defaults(self):
        """Test retrieving config with defaults"""
        configs = {}
        source_id = "unknown_source"
        
        config = ArtifactConfigLoader.get_config(configs, source_id)
        
        assert config.id == source_id
        assert config.base_package == "com.example.dao" # default
        assert config.datasource == "MainDS" # default

    def test_get_derived_packages(self):
        """Test derived package getters"""
        config = ArtifactConfig(id="test", base_package="com.base")
        
        assert config.get_dto_package() == "com.base.dto"
        assert config.get_dao_package() == "com.base"
        assert config.get_dao_name() == "GeneratedDao"
        
        custom_config = ArtifactConfig(
            id="test2",
            base_package="com.base",
            dto_package="com.custom.dto",
            dao_package="com.custom.dao",
            dao_name="CustomDao"
        )
        
        assert custom_config.get_dto_package() == "com.custom.dto"
        assert custom_config.get_dao_package() == "com.custom.dao"
        assert custom_config.get_dao_name() == "CustomDao"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
