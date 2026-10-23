"""Sauvegarde la date de la release dans release_date_backup quand original_date écrase year/month/day.

Option `singleton` : pour les imports -s, applique la first-release-date du recording
MusicBrainz (mb_trackid) à original_year/month/day, et à year/month/day si
`singleton_overwrite_date` (défaut : oui).

Option `compilation_as_tracks` : même traitement, piste par piste, pour les albums compilation
importés en mode standard (non-singleton). Demande confirmation si `confirm` (défaut : oui).
"""

from datetime import datetime

from beets import config, ui
from beets.plugins import BeetsPlugin

# Declared as `types: release_date_backup: date`: stored as a timestamp
FIELD = "release_date_backup"
DATE_FIELDS = ("year", "month", "day")


def release_date(info):
    """Timestamp de la date de release (mois/jour manquants = 1) ; None sans année."""
    if not info.year:
        return None
    return datetime(info.year, info.month or 1, info.day or 1).timestamp()


def parse_mb_date(value):
    """'YYYY[-MM[-DD]]' -> (year, month, day), 0 pour les parties absentes ; None si invalide."""
    try:
        parts = [int(p) for p in value.split("-")]
    except ValueError:
        return None
    if not parts or not 1 <= len(parts) <= 3:
        return None
    return tuple(parts + [0] * (3 - len(parts)))


class OriginalDateExtendedPlugin(BeetsPlugin):
    def __init__(self):
        super().__init__()
        self.config.add(
            {
                "singleton": False,
                "singleton_overwrite_date": True,
                "compilation_as_tracks": False,
                "confirm": True,
            }
        )
        self._dates = {}
        self._first_release_dates = {}
        self._compilation_tasks = set()
        if config["original_date"].get(bool):
            self.register_listener("import_task_choice", self.remember_date)
            self.register_listener("import_task_apply", self.backup_items)
            self.register_listener("album_imported", self.backup_album)
        else:
            self._log.debug("option original_date désactivée...")
        if self.config["singleton"].get(bool) or self.config[
            "compilation_as_tracks"
        ].get(bool):
            self.register_listener("mb_track_extract", self.remember_first_release_date)
        if self.config["singleton"].get(bool):
            self.register_listener("import_task_apply", self.apply_singleton_date)
        if self.config["compilation_as_tracks"].get(bool):
            self.register_listener("import_task_apply", self.apply_compilation_dates)
            # Runs after task.add(), whose album.store() pushes album dates onto items
            self.import_stages = [self.compilation_stage]

    def remember_first_release_date(self, data):
        # Raw recording payload from the musicbrainz plugin, before TrackInfo drops the date
        singletons = config["import"]["singletons"].get(bool)
        date = data.get("first_release_date") or data.get("first-release-date")
        self._log.debug(
            "mb_track_extract : recording id={} title={} first_release_date={}",
            data.get("id"),
            data.get("title"),
            date,
        )
        if self.config["singleton" if singletons else "compilation_as_tracks"].get(
            bool
        ):
            if date:
                self._first_release_dates[data["id"]] = date
        return {}

    def apply_singleton_date(self, session, task):
        # Only `beet import -s`, not tracks split off an album import ("as Tracks")
        if not config["import"]["singletons"].get(bool):
            return
        if task.is_album or not task.match:
            return
        item = task.item
        # CRUCIAL : On utilise le recording ID de Beets qui correspond au data["id"] de MusicBrainz
        recording_id = (
            item.get("mb_recordingid") or task.match.info.track_id or item.mb_trackid
        )
        self._log_ids(item, recording_id, track_id=task.match.info.track_id)
        self.apply_first_release_date(item, recording_id)

    def apply_compilation_dates(self, session, task):
        if config["import"]["singletons"].get(bool):
            return
        if not task.is_album or not task.match:
            return
        info = task.match.info
        albumtypes = [t.lower() for t in (info.albumtypes or [info.albumtype or ""])]
        self._log.debug("{} : va={} albumtypes={}", info.album, info.va, albumtypes)
        if not (info.va or "compilation" in albumtypes):
            return
        if (
            self.config["confirm"].get(bool)
            and not config["import"]["quiet"].get(bool)
            and not ui.input_yn(
                f"Appliquer la date d'origine de chaque recording à la compilation {info.album} ? (Y/n)",
                require=False,
            )
        ):
            return
        self._compilation_tasks.add(task)

    def compilation_stage(self, session, task):
        """Import stage : applique la first-release-date de chaque recording aux pistes d'une compilation.

        Pourquoi pas dans `import_task_apply` : `ImportTask.add()` s'exécute après cet
        événement et appelle `apply_album_metadata()` puis `album.store()`, qui recopie
        year/month/day/original_* de l'album sur toutes les pistes et écrase les dates
        par piste. Les import stages de plugin tournent après `add()` et avant
        `manipulate_files()` (déplacement + écriture des tags), donc les dates posées ici
        sont conservées en base et écrites dans les fichiers.

        La confirmation utilisateur reste dans `apply_compilation_dates()` (stage
        `user_query`, séquentiel) : demander ici risquerait d'entrelacer la question avec
        le prompt de l'album suivant, les stages tournant en parallèle.
        """
        # Only tasks confirmed in apply_compilation_dates()
        if task not in self._compilation_tasks:
            return
        self._compilation_tasks.discard(task)
        for item in task.imported_items():
            # CRUCIAL : le morceau de la compilation doit être trouvé par son Recording ID
            recording_id = item.get("mb_recordingid") or item.mb_trackid
            self._log_ids(item, recording_id)
            self.apply_first_release_date(item, recording_id)
            # plugin_stage() reloads items from the DB right after this stage
            item.store()

    def _log_ids(self, item, recording_id, **extra):
        self._log.debug(
            "{} : mb_recordingid={} mb_trackid={} mb_releasetrackid={} mb_albumid={} {}-> lookup {}",
            item.title,
            item.get("mb_recordingid"),
            item.get("mb_trackid"),
            item.get("mb_releasetrackid"),
            item.get("mb_albumid"),
            "".join(f"{k}={v} " for k, v in extra.items()),
            recording_id,
        )

    def apply_first_release_date(self, item, recording_id):
        if not recording_id:
            return
        raw = self._first_release_dates.get(recording_id)
        self._log.debug(
            "lookup {} -> {} ({} recordings mémorisés)",
            recording_id,
            raw,
            len(self._first_release_dates),
        )
        date = parse_mb_date(raw) if raw else None
        if date is None:
            self._log.info(
                "pas de first-release-date pour {} ({})", item.title, recording_id
            )
            return
        overwrite = self.config["singleton_overwrite_date"].get(bool)
        for field, value in zip(DATE_FIELDS, date):
            if overwrite:
                item[field] = value
            item["original_" + field] = value
        self._log.info(
            "{} - {} : first recording date {}", item.artist, item.title, raw
        )

    def remember_date(self, session, task):
        # Fired before apply_metadata: the chosen release still carries its own date
        if not task.is_album or not task.match:
            return
        info = task.match.info
        date = release_date(info)
        if info.album_id and date is not None:
            self._dates[info.album_id] = date
            self._log.debug(
                "{} : date de release {} mémorisée en RAM",
                info.album_id,
                datetime.fromtimestamp(date).date(),
            )

    def backup_items(self, session, task):
        if not task.is_album or not task.match:
            return
        info = task.match.info
        date = self._dates.pop(info.album_id, None)
        if date is None:
            self._log.info(
                "aucune date de release mémorisée pour {} ({})",
                info.album,
                info.album_id,
            )
            return
        for item in task.items:
            item[FIELD] = date
        self._log.info(
            "{} = {} (original_year {}, {} morceaux)",
            FIELD,
            datetime.fromtimestamp(date).date(),
            info.original_year,
            len(task.items),
        )

    def backup_album(self, lib, album):
        dates = {item.get(FIELD) for item in album.items()} - {None}
        if len(dates) == 1:
            album[FIELD] = dates.pop()
            album.store()

