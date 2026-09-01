"""Module for handling logging and console output capture."""

# Standard library imports
import sys
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import TextIO

LOGGING_DIRECTORY = Path("logs")
LOGGING_DIRECTORY.mkdir(exist_ok=True)

# Emoji with a variation selector (U+FE0F) whose display width many terminals
# miscalculate, visually "eating" the space right after them. Compensated with
# an extra space on terminal output only - the saved log file keeps the
# canonical single-space text from app.i18n.
_TERMINAL_SPACING_FIXES = {
    "🗂️ ": "🗂️  ",
    "🗑️ ": "🗑️  ",
    "🖥️ ": "🖥️  ",
}


class ConsoleCapture:
    """
    Context manager to capture console output and save to file.

    This class implements a context manager that redirects stdout to capture
    all console output and simultaneously write it to both the console and a file.

    Attributes
    ----------
    filename : str
        Path to the output file.
    original_stdout : TextIO
        Reference to the original stdout.
    file : TextIO | None
        File handle for output file.
    """

    filename: str
    original_stdout: TextIO
    file: TextIO | None = None

    def __init__(self, filename: str | None = None):
        """
        Initialize the ConsoleCapture with the target filename.

        Parameters
        ----------
        filename : str | None, optional
            Path to the file where console output will be saved. Defaults to
            a timestamped file under `logs/` when not provided.
        """
        if filename is None:
            filename = str(LOGGING_DIRECTORY /
                           datetime.now().strftime("%d-%m-%Y_%H.%M.%S.log"))

        self.filename = filename

        self.original_stdout = sys.stdout

        self.file: TextIO | None = None

    def __enter__(self):
        """
        Enter the context manager and start capturing console output.

        Returns
        -------
        ConsoleCapture
            Self instance for use in the `with` statement.
        """
        self.file = open(self.filename, 'w', encoding='utf-8')
        sys.stdout = self

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None
    ):
        """
        Exit the context manager and restore original console output.

        Parameters
        ----------
        exc_type : type[BaseException] | None
            Exception type if an exception occurred.
        exc_val : BaseException | None
            Exception value if an exception occurred.
        exc_tb : TracebackType | None
            Exception traceback if an exception occurred.
        """
        sys.stdout = self.original_stdout

        if self.file:
            self.file.close()

    def write(self, text: str):
        """
        Write text to both console and file simultaneously.

        The console copy gets a terminal-rendering compensation (see
        `_TERMINAL_SPACING_FIXES`); the file always keeps the original text.

        Parameters
        ----------
        text : str
            Text to write to both outputs.
        """
        terminal_text = text
        for original, padded in _TERMINAL_SPACING_FIXES.items():
            terminal_text = terminal_text.replace(original, padded)

        self.original_stdout.write(terminal_text)

        if self.file:
            self.file.write(text)

    def flush(self):
        """Flush both console and file output buffers."""
        self.original_stdout.flush()

        if self.file:
            self.file.flush()


def delete_logs(exclude: Path | None = None) -> list[Path]:
    """
    Delete every saved run log under `LOGGING_DIRECTORY`.

    Parameters
    ----------
    exclude : Path | None, optional
        A log file to keep - the current run's own log, still open for
        writing under an active `ConsoleCapture`. Deleting it out from under
        that open file handle would silently discard this very deletion's
        own record once the run finishes and closes it.

    Returns
    -------
    list[Path]
        Paths of the log files that were deleted.
    """
    to_delete = [
        path for path in LOGGING_DIRECTORY.glob("*.log")
        if path != exclude
    ]

    for path in to_delete:
        path.unlink()

    return to_delete
