# Developer Guide & Architectural Standards

This document defines the development standards and architectural patterns for the `proc_parser_antigravity` project. **All AI Agents and Developers must follow these rules.**

## 1. Core Principles

### 1.1. Modularity
- **Rule**: Every new feature MUST be implemented as a separate module.
- **Reasoning**: To prevent code entanglement and ensure easy maintenance and testing.

### 1.2. Independence
- **Rule**: Modules MUST operate independently. They should not rely on the internal state of other modules unless explicitly passed through defined interfaces.
- **Reasoning**: To avoid "spaghetti code" and side effects where changing one part of the system breaks another.

## 2. Main Logic & Plugin Architecture

The core architectural pattern for this project is the **Main Logic + Plugin** pattern.

### 2.1. The Pattern
1.  **Main Logic**: Defines the primary flow of control. It performs the essential task (e.g., merging functions, parsing a file).
2.  **Plugins**: Encapsulate *additional* or *optional* behavior. They are extensions that modify or enhance the main logic without changing the main logic's code.

### 2.2. Rules for Implementation
- **Main Logic**:
    - MUST define an extension point (hook) where plugins can be executed.
    - MUST NOT hardcode specific feature logic if that logic can be optional.
    - MUST provide a mechanism to load plugins dynamically or explicitly.
- **Plugins**:
    - MUST implement a standard interface defined by the Main Logic.
    - MUST reside in a `plugins/` subdirectory relative to the module they extend.
    - MUST be loaded only when needed.

### 2.3. Example Structure
```
my_module/
├── core.py           # Main Domain Logic
├── plugin_interface.py # Interface definition (Abstract Base Class)
└── plugins/          # Plugin implementations
    ├── __init__.py
    ├── feature_a.py
    └── feature_b.py
```

### 2.4. Code Pattern Example

**Interface (`plugin_interface.py`):**
```python
from abc import ABC, abstractmethod

class MyFunctionPlugin(ABC):
    @abstractmethod
    def apply(self, context: dict) -> dict:
        """Modify the context or perform an action."""
        pass
```

**Main Logic (`core.py`):**
```python
class MainProcessor:
    def __init__(self):
        self.plugins = []

    def register_plugin(self, plugin: MyFunctionPlugin):
        self.plugins.append(plugin)

    def process(self, data):
        # 1. Base Logic
        result = self._core_logic(data)
        
        # 2. Plugin Execution
        for plugin in self.plugins:
            result = plugin.apply(result)
            
        return result
```

## 3. Utility Functions

Utility functions should be organized logically to maintain a clean codebase.

### 3.1. Standard Utilities
- **Rule**: Standard utility functions that are pure and do not depend on the domain logic (e.g., string formatting, date calculation, file system helpers) MUST be organized into `utils/` directories.
- **Placement**:
    - **Local Utilities**: If a utility is used by only one module, place it in `[module_name]/utils/`.
    - **Global Utilities**: If a utility is shared by multiple modules, place it in the project-level `infra/utils/` or `common/utils/`.
- **Naming**: Use descriptive filenames within the `utils/` directory (e.g., `string_utils.py`, `path_utils.py`).

## 4. Agent Instructions

**System Prompt Injection**:
When asking an AI Agent to work on this codebase, ensure the following rule is active:

> "Always follow the architectural patterns and rules defined in `proc_parser/DEVELOPER_GUIDE.md`."

---
*Last Updated: 2026-01-18*
