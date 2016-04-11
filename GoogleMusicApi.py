import utils
from GoogleMusicStorage import storage

class GoogleMusicApi():
    def __init__(self):
        self.api      = None
        self.device   = None
        self.login    = None

    def getApi(self,nocache=False):
        if self.api == None :
            import GoogleMusicLogin
            self.login = GoogleMusicLogin.GoogleMusicLogin()
            self.login.login(nocache)
            self.api = self.login.getApi()
            self.device = self.login.getDevice()
        return self.api

    def getDevice(self):
        if self.device == None:
            self.getApi()
        return self.device

    def getLogin(self):
        if self.login == None:
            self.getApi()
        return self.login

    def clearCache(self):
        storage.clearCache()

    def clearCookie(self):
        self.getLogin().clearCookie()

    def getPlaylistSongs(self, playlist_id, forceRenew=False):
        if playlist_id in ('thumbsup','lastadded','mostplayed','freepurchased','feellucky'):
            songs = storage.getAutoPlaylistSongs(playlist_id)
            if playlist_id == 'thumbsup':
                """ Try to fetch store thumbs up songs """
                songs.extend(self._loadStoreTracks(self.getApi().get_promoted_songs()))
        else:
            if forceRenew:
                self.updatePlaylistSongs()
            songs = storage.getPlaylistSongs(playlist_id)

        return songs

    def getPlaylistsByType(self, playlist_type, forceRenew=False):
        if forceRenew:
            self.updatePlaylistSongs()

        return storage.getPlaylists()

    def getSong(self, song_id):
        return storage.getSong(song_id)

    def loadLibrary(self):
        gen = self.getApi().get_all_songs(incremental=True)

        for chunk in gen:
            utils.log("Chunk Size: "+repr(len(chunk)))
            storage.storeInAllSongs(chunk)

        self.updatePlaylistSongs()

        if utils.addon.getSetting('load_kodi_library')=='true':
            try:
                storage.loadKodiLib()
            except Exception as ex:
                utils.log("ERROR trying to load local library: "+repr(ex))

        import time
        utils.addon.setSetting("fetched_all_songs", str(time.time()))


    def updatePlaylistSongs(self):
        storage.storePlaylistSongs(self.getApi().get_all_user_playlist_contents())

    def getSongStreamUrl(self, song_id):
        stream_url = self.getLogin().getStreamUrl(song_id)
        return stream_url

    def incrementSongPlayCount(self, song_id):
        try:
            self.getApi().increment_song_playcount(song_id)
        except Exception as ex:
            utils.log("ERROR trying to increment playcount: "+repr(ex))
        storage.incrementSongPlayCount(song_id)

    def createPlaylist(self, name):
        playlist_id = self.getApi().create_playlist(name)
        storage.createPlaylist(name, playlist_id)

    def deletePlaylist(self, playlist_id):
        self.getApi().delete_playlist(playlist_id)
        storage.deletePlaylist(playlist_id)

    def setThumbs(self, song_id, thumbs):
        if song_id[0] == 'T':
            song = self.getApi().get_track_info(song_id)
            song['rating'] = thumbs
            self.getApi().change_song_metadata(song)
        else:
            self.getApi().change_song_metadata({'id':song_id,'rating':thumbs})
        storage.setThumbs(song_id, thumbs)

    def getFilterSongs(self, filter_type, filter_criteria, albums):
        return storage.getFilterSongs(filter_type, filter_criteria, albums)

    def getCriteria(self, criteria, artist=''):
        return storage.getCriteria(criteria,artist)

    def getSearch(self, query):
        utils.log("API getsearch: "+query)
        result = storage.getSearch(query)
        tracks = result['tracks']
        albums = result['albums']
        artists = result['artists']
        try:
            store_result = self.getApi().search_all_access(query)
            #utils.log("API getsearch aa: "+repr(store_result))
            tracks.extend(self._loadStoreTracks(store_result['song_hits']))
            albums.extend(self._loadStoreAlbums(store_result['album_hits']))
            for artist in store_result['artist_hits']:
                artists.append(artist['artist'])
            utils.log("API search results: tracks "+repr(len(tracks))+" albums "+repr(len(albums))+" artists "+repr(len(artists)))
        except Exception as e:
            utils.log("*** NO ALL ACCESS RESULT IN SEARCH *** "+repr(e))
        return result

    def getAlbum(self, albumid):
        return self._loadStoreTracks(self.getApi().get_album_info(albumid, include_tracks=True)['tracks'])

    def getArtist(self, artistid, relartists=0):
        if relartists == 0:
            return self._loadStoreTracks(self.getApi().get_artist_info(artistid, include_albums=False, max_top_tracks=50, max_rel_artist=0)['topTracks'])
        else:
            return self.getApi().get_artist_info(artistid, include_albums=False, max_top_tracks=0, max_rel_artist=relartists)['related_artists']

    def getTrack(self, trackid):
        return self._convertStoreTrack(self.getApi().get_track_info(trackid))

    def getSharedPlaylist(self, sharetoken):
        return self._loadStoreTracks(self.getApi().get_shared_playlist_contents(sharetoken))

    def getStations(self):
        stations = {}
        try:
            stations = self.getApi().get_all_stations()
            utils.log("STATIONS: "+repr(stations))
        except Exception as e:
            utils.log("*** NO STATIONS *** "+repr(e))
        return stations

    def getStationTracks(self, station_id):
        return self._loadStoreTracks(self.getApi().get_station_tracks(station_id, num_tracks=200))

    def startRadio(self, name, song_id):
        return self.getApi().create_station(name, track_id=song_id)

    def addAAtrack(self, song_id):
        self.getApi().add_aa_track(song_id)

    def addToPlaylist(self, playlist_id, song_id):
        entry_id = self.getApi().add_songs_to_playlist(playlist_id, song_id)
        storage.addToPlaylist(playlist_id, song_id, entry_id[0])

    def delFromPlaylist(self, playlist_id, song_id):
        entry_id = storage.delFromPlaylist(playlist_id, song_id)
        self.getApi().remove_entries_from_playlist(entry_id)

    def getTopcharts(self, content_type='tracks'):
        content = self.getApi().get_top_chart()
        if content_type == 'tracks':
            return self._loadStoreTracks(content['tracks'])
        if content_type == 'albums':
            return self._loadStoreAlbums(content['albums'])

    def getNewreleases(self):
        return self._loadStoreAlbums(self.getApi().get_new_releases())

    def _loadStoreAlbums(self, store_albums):
        albums = []
        for item in store_albums:
            utils.log(repr(item))
            if 'album' in item:
                item = item['album']
            albums.append(item)
        return albums

    def _loadStoreTracks(self, tracks):
        result = []
        artistInfo = {}
        miss = 0

        for track in tracks:
            try:
                if 'track' in track:
                    track = track['track']
                if not 'artistArtRef' in track and 'artistId' in track:
                    artistId = track['artistId'][0]
                    if not artistId in artistInfo:
                        miss = miss + 1
                        artistInfo[artistId] = self.getApi().get_artist_info(artistId, include_albums=False, max_top_tracks=0, max_rel_artist=0)
                    if 'artistArtRefs' in artistInfo[artistId]:
                        track['artistArtRef'] = artistInfo[artistId]['artistArtRefs']
                result.append(self._convertStoreTrack(track))
            except Exception as e:
                utils.log("*** ERROR LOADING STORE TRACK *** "+repr(e))

        utils.log("Loaded %d tracks (%d art miss)" % (len(tracks), miss) )
        return result


    def _convertStoreTrack(self, aaTrack):
        return { 'song_id':       aaTrack.get('id') or aaTrack['storeId'],
                 'album':         aaTrack.get('album'),
                 'title':         aaTrack['title'],
                 'year':          aaTrack.get('year', 0),
                 'rating':        aaTrack.get('rating', 0),
                 'album_artist':  aaTrack.get('albumArtist'),
                 'tracknumber':   aaTrack.get('trackNumber'),
                 'playcount':     aaTrack.get('playCount', 0),
                 'artist':        aaTrack.get('artist'),
                 'genre':         aaTrack.get('genre'),
                 'discnumber':    aaTrack.get('discNumber'),
                 'duration':      int(aaTrack.get('durationMillis',0))/1000,
                 'albumart':      aaTrack['albumArtRef'][0]['url'] if aaTrack.get('albumArtRef') else utils.addon.getAddonInfo('icon'),
                 'display_name':  aaTrack.get('artist')+" - "+aaTrack['title'],
                 'artistart':     aaTrack['artistArtRef'][0]['url'] if aaTrack.get('artistArtRef') else utils.addon.getAddonInfo('fanart')
                }

