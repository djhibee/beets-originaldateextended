from beets.plugins import BeetsPlugin
from beets import config

class OriginalDateExtendedPlugin(BeetsPlugin):
    def __init__(self):
        super(OriginalDateExtendedPlugin, self).__init__()
        
        # Verification si original_date est active
        if config['original_date'].get(bool):
            # Enregistrement sur l evenement avant l ecriture finale
            self.register_listener('import_task_choice', self.backup_release_year)

    def backup_release_year(self, session, task):
        # Verification de la presence d un album valide
        if task.match and task.match.info:
            album_info = task.match.info
            
            # Recupere l annee de l edition avant sa modification
            if hasattr(album_info, 'year') and album_info.year:
                # Sauvegarde dans les attributs flexibles de l album
                task.album_attributes['release_year_backup'] = str(album_info.year)
                self._log.debug(f"Backup annee edition: {album_info.year}")

