from fman import DirectoryPaneListener
from fman.url import normalize
from fman.impl.model.model import Model, transaction
from fman.url import join
import re


@transaction(priority=1)
def _init(self, callback):
    files = [self._init_file(join(self._location, '..'))]
    try:
        file_names = iter(self._fs.iterdir(self._location))
    except FileNotFoundError:
        self.location_disappeared.emit(self._location)
        return
    else:
        while not self._shutdown:
            try:
                file_name = next(file_names)
            except FileNotFoundError:
                self.location_disappeared.emit(self._location)
                return
            except (StopIteration, OSError):
                break
            else:
                url = join(self._location, file_name)
                try:
                    file_ = self._init_file(url)
                except OSError:
                    continue

                files.append(file_)
        else:
            assert self._shutdown
            return

        preloaded_files = self._sorted(self._filter(files))
        for i in range(min(self._num_rows_to_preload, len(preloaded_files))):
            if self._shutdown:
                return
            try:
                preloaded_files[i] = self._load_file(preloaded_files[i].url)
            except FileNotFoundError:
                pass

        self._on_rows_inited(files, preloaded_files, callback)
        self.location_loaded.emit(self._location)
        self._file_watcher.start()
        self._load_remaining_files()


@transaction(priority=5)
def reload_(self):
    self._fs.clear_cache(self._location)
    files = [self._init_file(join(self._location, '..'))]
    try:
        file_names = iter(self._fs.iterdir(self._location))
    except FileNotFoundError:
        self.location_disappeared.emit(self._location)
        return
    else:
        while not self._shutdown:
            try:
                file_name = next(file_names)
            except FileNotFoundError:
                self.location_disappeared.emit(self._location)
                return
            except (StopIteration, OSError):
                break
            else:
                url = join(self._location, file_name)
                try:
                    try:
                        file_before = self._files[url]
                    except KeyError:
                        file_ = self._init_file(url)
                    else:
                        if file_before.is_loaded:
                            file_ = self._load_file(url)
                        else:
                            file_ = self._init_file(url)
                except FileNotFoundError:
                    continue

                files.append(file_)
        else:
            assert self._shutdown
            return

        self._on_files_reloaded(files)
        self._load_remaining_files()


Model._init = _init
Model.reload = reload_

class DottedPaneListener(DirectoryPaneListener):
    def before_location_change(self, url, sort_column='', ascending=True):
        if not url.endswith('/..'):
            return
        # normalize works weird with "C://.."
        if re.match(r'file://\w:\/\.\.', url):
            url = url[:-2]
            return url, sort_column, ascending
        url = normalize(url)
        if url == 'file://':
            url = 'file:///'
        if url.endswith('/..'):
            url = url[:-2]
        return url, sort_column, ascending


from core import commands
_hidden_file_filter_orig = commands._hidden_file_filter


def _hidden_file_filter(url):
    if url.endswith('/..'):
        return True
    return _hidden_file_filter_orig(url)

commands._hidden_file_filter = _hidden_file_filter
