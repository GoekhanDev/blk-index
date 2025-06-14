import logging
import sys

logger = logging.getLogger('blockchain_explorer')
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(
    logging.Formatter('%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s')
)
logger.addHandler(handler)

error = logger.error
info = logger.info
debug = logger.debug
warning = logger.warning