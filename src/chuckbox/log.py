import logging

_LOG_LEVEL_NOTSET = 'NOTSET'


def get_logger(logger_name):
    return _LOGGING_MANAGER.get_logger(logger_name)


def get_log_manager():
    return _LOGGING_MANAGER


def _cfg_var_exists(cfg, var_name):
    var = None

    if isinstance(cfg, dict):
        var = cfg.get(var_name)
    elif hasattr(cfg, var_name):
        var = getattr(cfg, var_name)

    return var is not None


class LoggingConfig(object):

    def __init__(self):
        self.logfile = None
        self.level = 'INFO'
        self.console_enabled = True


class LoggingManager(object):

    def __init__(self):
        self._root_logger = logging.getLogger()
        self._handlers = list()

    def _add_handler(self, handler):
        self._handlers.append(handler)
        self._root_logger.addHandler(handler)

    def _clean_handlers(self):
        [self._root_logger.removeHandler(hdlr) for hdlr in self._handlers]
        del self._handlers[:]

    def configure(self, cfg):
        self._clean_handlers()

        # Should we write to a logfile?
        if _cfg_var_exists(cfg, 'logfile'):
            self._add_handler(logging.FileHandler(cfg['logfile']))

        # Is console output enabled?
        if _cfg_var_exists(cfg, 'console_enabled'):
            if cfg['console_enabled'] is True:
                self._add_handler(logging.StreamHandler())

        # How verbose should we be?
        if _cfg_var_exists(cfg, 'level'):
            level = cfg['level']
            self._root_logger.setLevel(level)
            self._root_logger.info('Logging level set to: {level}'.format(
                level=level))

    def get_logger(self, logger_name):
        logger = logging.getLogger(logger_name)
        logger.setLevel(_LOG_LEVEL_NOTSET)
        return logger


globals()['_LOGGING_MANAGER'] = LoggingManager()
