import re
from patterns import PATTERN_HOST_VAR

class SQLConverter:
    @staticmethod
    def normalize_sql(raw_sql):
        """
        Convert Pro*C SQL to standard SQL.
        Extract host variables and replace them with placeholders.
        """
        # Remove newlines and extra spaces for easier processing
        clean_sql = re.sub(r'\s+', ' ', raw_sql).strip()
        
        # Determine SQL Type
        sql_type = "UNKNOWN"
        first_word = clean_sql.split(' ')[0].upper()
        if first_word in ["SELECT", "INSERT", "UPDATE", "DELETE", "DECLARE", "OPEN", "FETCH", "CLOSE", "PREPARE", "EXECUTE", "CONNECT", "COMMIT", "ROLLBACK"]:
            sql_type = first_word
        
        input_vars = []
        output_vars = []
        
        # Handle INTO clause (Output variables)
        # Pattern: SELECT ... INTO :a, :b FROM ...
        # We need to extract INTO clause and remove it from normalized SQL
        into_match = re.search(r'\s+INTO\s+(.*?)\s+FROM', clean_sql, re.IGNORECASE)
        if into_match:
            into_clause = into_match.group(1)
            # Extract vars from INTO clause
            for match in PATTERN_HOST_VAR.finditer(into_clause):
                output_vars.append(match.group(0))
            
            # Remove INTO clause for normalized SQL
            normalized_sql = re.sub(r'\s+INTO\s+.*?\s+FROM', ' FROM', clean_sql, flags=re.IGNORECASE)
        else:
            # Check for FETCH ... INTO ...
            fetch_into_match = re.search(r'FETCH\s+.*?\s+INTO\s+(.*)', clean_sql, re.IGNORECASE)
            if fetch_into_match:
                 into_clause = fetch_into_match.group(1)
                 for match in PATTERN_HOST_VAR.finditer(into_clause):
                    output_vars.append(match.group(0))
                 normalized_sql = clean_sql # Keep FETCH structure but maybe remove INTO? usually FETCH is specific.
            else:
                normalized_sql = clean_sql

        # Handle Input variables (Host vars in WHERE, VALUES, etc.)
        # We scan the normalized SQL (which might still have host vars)
        # We need to be careful not to re-capture output vars if we didn't remove them perfectly,
        # but if we removed INTO clause, they should be gone.
        
        # Edge case: HH:MM:SS
        # We iterate all matches and check context
        def replace_host_var(match):
            var_name = match.group(0)
            start = match.start()
            
            # Check if it looks like a time string (preceded by digit and colon? no, colon is part of match)
            # Check if the character before the match is a digit (e.g. 12:30)
            # match.string is the whole string
            if start > 0 and match.string[start-1].isdigit():
                return var_name # It's likely time, don't replace
            
            input_vars.append(var_name)
            return "?" # Standard placeholder
            
        normalized_sql = PATTERN_HOST_VAR.sub(replace_host_var, normalized_sql)
        
        # Dynamic SQL Handling
        dynamic_sql_stmt = None
        if sql_type == "PREPARE":
            # PREPARE s1 FROM :stmt;
            match = re.search(r'FROM\s+(:?\w+)', clean_sql, re.IGNORECASE)
            if match:
                dynamic_sql_stmt = match.group(1)
        elif sql_type == "EXECUTE":
             # EXECUTE s1 USING :v1;
             pass # input vars are already handled by generic scanner

        return {
            "type": "sql",
            "sql_type": sql_type,
            "raw_sql": raw_sql,
            "normalized_sql": normalized_sql,
            "input_host_vars": input_vars,
            "output_host_vars": output_vars,
            "dynamic_sql_stmt": dynamic_sql_stmt
        }

