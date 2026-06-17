from abc import ABC, abstractmethod

class TelegramInterface(ABC):

    @abstractmethod
    def send_alert(self, message: str) -> bool:
        """Sends normal market signal alert message to admin."""
        pass

    @abstractmethod
    def send_admin_warning(self, message: str) -> bool:
        """Sends admin critical alerts or warnings (e.g. Ghost Mode triggers)."""
        pass
