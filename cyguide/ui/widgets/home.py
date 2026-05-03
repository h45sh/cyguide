"""Home widget to display session overview."""

from textual.widgets import Static

class GraphOverview(Static):
    """A widget showing the current count of nodes by type."""
    
    def on_mount(self):
        self.update("Graph contains nodes of various types (Real-time stats coming soon)...")
