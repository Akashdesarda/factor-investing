import logging

from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import install

install(show_locals=True)
logger = logging.getLogger("factor-investing")
console_handler = RichHandler(
    markup=True,
    show_path=False,
    console=Console(),
    locals_max_string=150,
)
log_format = logging.Formatter(
    "%(asctime)s\t%(message)s", datefmt="%d-%b-%y %H:%M:%S"
)
console_handler.setFormatter(log_format)
logger.addHandler(console_handler)
logger.setLevel(logging.DEBUG)
