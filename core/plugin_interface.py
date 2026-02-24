from abc import ABC, abstractmethod
from typing import List, Any, TypeVar, Generic

T = TypeVar('T')  # The type of the context/data being processed

class PluginInterface(ABC, Generic[T]):
    """
    Abstract base class for all plugins in the system.
    Plugins should inherit from a specific subclass of this interface
    defined by the module they are extending.
    """
    
    @abstractmethod
    def name(self) -> str:
        """Return the unique name of the plugin."""
        pass

    @abstractmethod
    def description(self) -> str:
        """Return a brief description of what the plugin does."""
        pass

    @abstractmethod
    def apply(self, context: T) -> T:
        """
        Apply the plugin's logic to the given context.
        
        Args:
            context: The data or object being processed.
            
        Returns:
            The modified context (or the original if no changes were made).
        """
        pass


class PluginManager(Generic[T]):
    """
    Manages the registration and execution of plugins.
    """
    def __init__(self):
        self._plugins: List[PluginInterface[T]] = []

    def register_plugin(self, plugin: PluginInterface[T]):
        """Register a new plugin instance."""
        if not isinstance(plugin, PluginInterface):
            raise TypeError(f"Plugin must inherit from PluginInterface, got {type(plugin)}")
        self._plugins.append(plugin)
        print(f"Plugin registered: {plugin.name()}")

    def apply_all(self, context: T) -> T:
        """
        Apply all registered plugins sequentially to the context.
        """
        for plugin in self._plugins:
            # Optional: Add logging or error handling here
            try:
                context = plugin.apply(context)
            except Exception as e:
                print(f"Error executing plugin {plugin.name()}: {e}")
                # Decide whether to raise or continue based on policy. 
                # For now, we continue to ensure robustness.
        return context

    def get_plugins(self) -> List[PluginInterface[T]]:
        """Return the list of registered plugins."""
        return self._plugins

    def clear_plugins(self):
        """Unregister all plugins."""
        self._plugins = []
