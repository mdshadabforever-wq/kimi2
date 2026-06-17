from abc import ABC, abstractmethod

class SlackInterface(ABC):

    @abstractmethod
    def send_alert(self, message: str) -> bool:
        """Sends a signal alert message to the configured Slack channel."""
        pass

    @abstractmethod
    def send_admin_warning(self, message: str) -> bool:
        """Sends an admin warning (Ghost Mode, risk breach, etc.) to Slack."""
        pass
