import corio
from corio import sets

from package.paths import paths


class Settings(sets.Base):
    paths = paths

    def run(self):
        super().run()

        from corio import debug
        debug.trace()
        from package.obs import logger

        logger.info(f"Launching {paths.name} {paths.metadata.version=} {corio.get_version()=} from entrypoint.")
        logger.debug(f"{paths.settings.exists()=} {str(paths.settings)=}")


settings = Settings()
settings
