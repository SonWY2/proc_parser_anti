import re
from abc import ABC, abstractmethod

class ParserPlugin(ABC):
    """
    Abstract base class for Pro*C parser plugins.
    Plugins are used to parse custom constructs or project-specific syntax.
    """
    
    @property
    @abstractmethod
    def pattern(self):
        """
        Regular expression pattern to match.
        Should be a compiled regex object or a string.
        """
        pass
    
    @property
    @abstractmethod
    def element_type(self):
        """
        The 'type' string for the extracted element (e.g., 'bam_call').
        """
        pass

    @abstractmethod
    def parse(self, match, content):
        """
        Extract data from the regex match object.
        
        Args:
            match: The regex match object.
            content: The full content of the file (useful for line counting).
            
        Returns:
            dict: A dictionary containing the extracted data. 
                  Must include 'type', 'line_start', 'line_end', 'raw_content'.
        """
        pass

    def get_line_range(self, match, content):
        """
        Helper to calculate line start and end from a match.
        """
        start_index = match.start()
        end_index = match.end()
        
        line_start = content.count('\n', 0, start_index) + 1
        line_end = content.count('\n', 0, end_index) + 1
        
        return line_start, line_end
