from bitsharesextra.storage import DataDir

import os
import logging
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

class ChatRooms(DataDir):
    """
    """
    __tablename__ = 'chatrooms'
    __columns__ = [ 'id', 'name', 'pub', 'server' ]

    def __init__(self, *args, **kwargs):
        super(ChatRooms, self).__init__(*args, **kwargs)

    def create(self):
        """ Create the new table in the SQLite database
        """
        query = ('CREATE TABLE %s (' % self.__tablename__ +
                 'id INTEGER PRIMARY KEY AUTOINCREMENT,' +
                 'name TEXT,' +
                 'pub STRING(256),' +
                 'server STRING(512)'
                 ')',)
        self.sql_execute(query)

    def getRooms(self):
        """ Returns all entries stored in the database
        """
        query = ("SELECT " +
            (",".join(self.__columns__)) +
            (" FROM %s " % self.__tablename__)
            ,
        )
        rows = self.sql_fetchall(query)
        return self.sql_todict(self.__columns__, rows)

    def getBy(self, **kwargs):
        """ Return single entry by internal database id
        """
        v = list()
        w = [ ]
        for k in kwargs.keys():
            w.append(k+"=?")
            v.append(kwargs[k])
        query = ("SELECT " +
            (",".join(self.__columns__)) +
            (" FROM %s " % self.__tablename__) +
            "WHERE " + " AND ".join(w),
            v
        )
        row = self.sql_fetchone(query)
        if not row: return None
        return self.sql_todict(self.__columns__, [row])[0]

    def add(self, room_name, public_key, server):
        """ Add a room

           :param str room_name: Room name
        """
        if self.getBy(pub=public_key, server=server):
            raise ValueError("Room already in storage")
        query = ('INSERT INTO %s (name, pub, server) ' % self.__tablename__ +
                 'VALUES (?, ?, ?)',
                 (room_name, str(public_key), server))
        self.sql_execute(query)

