from bitshares.storage import SQLiteExtendedStore
from bitshares.storage import SqliteBlindHistoryStore
from graphenestorage import SQLiteCommon, SQLiteFile
from graphenestorage import SqliteEncryptedKeyStore
from graphenestorage import SqliteConfigurationStore
from appdirs import user_data_dir, system
import json

import os
import logging
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
#log.addHandler(logging.StreamHandler())

timeformat = "%Y%m%d-%H%M%S"

# sqlite3 is supposed to be thread-safe (unless you share single
# database connections, which we don't do), however it's possible
# to compile sqlite3 without this feature.

from PyQt5.QtCore import QMutex
main_mutex = QMutex()
muties = { }
def get_mutex(p : SQLiteExtendedStore, mod=""):
    k = p.sqlDataBaseFile + mod
    main_mutex.lock()
    m = muties.get(k, None)
    if not m:
        m = QMutex()
        muties[k] = m
    main_mutex.unlock()
    return m

class DataDir(SQLiteExtendedStore):
    """ This class ensures that the user's data is stored in its OS
        preotected user directory:

        **OSX:**

         * `~/Library/Application Support/<AppName>`

        **Windows:**

         * `C:\\Documents and Settings\\<User>\\Application Data\\Local Settings\\<AppAuthor>\\<AppName>`
         * `C:\\Documents and Settings\\<User>\\Application Data\\<AppAuthor>\\<AppName>`

        **Linux:**

         * `~/.local/share/<AppName>`

         Furthermore, it offers an interface to generated backups
         in the `backups/` directory every now and then.
    """
    appname = "bitshares"
    appauthor = "Fabian Shuch"
    storageDatabaseDefault = "bitshares.sqlite"

    @classmethod
    def preflight(self, filename=True):
        d = user_data_dir(self.appname, self.appauthor)
        if "linux" in system:
            d = os.path.expanduser("~/.bitshares/")
        if not(os.path.isdir(d)): # Hack - create directory in advance
            os.makedirs(d, exist_ok=True)
        if not filename:
            return d
        return os.path.join(d, self.storageDatabaseDefault)

    def column_exists(self, colname):
        query = ("SELECT %s FROM %s" % (colname, self.__tablename__), ())
        try:
            self.sql_fetchall(query)
        except:
            print("No such column `%s` in table %s" % (colname, self.__tablename__))
            return False
        return True

    def add_column(self, colname, sqltype):
        if self.column_exists(colname): return
        query = ("ALTER TABLE %s ADD COLUMN %s %s" % (self.__tablename__, colname, sqltype), )
        self.sql_execute(query)

    def poke(self):
        m = get_mutex(self)
        m.lock()
        try:
            r = SQLiteFile.poke(self)
        finally:
            m.unlock()
        return r

    def sql_fetchone(self, query):
        m = get_mutex(self)
        m.lock()
        try:
            r = SQLiteCommon.sql_fetchone(self, query)
        finally:
            m.unlock()
        return r

    def sql_fetchall(self, query):
        m = get_mutex(self)
        m.lock()
        try:
            r = SQLiteCommon.sql_fetchall(self, query)
        finally:
            m.unlock()
        return r

    def sql_execute(self, *args, **kwargs):
        m = get_mutex(self)
        m.lock()
        try:
            r = SQLiteCommon.sql_execute(self, *args, **kwargs)
        finally:
            m.unlock()
        return r

# Since those classed do not inherit DataDir, monkey-patch them.
# NOTE: it is very important that this happens before any of those classes
#  gets initialized.
for r in [ SqliteBlindHistoryStore, SqliteEncryptedKeyStore, SqliteConfigurationStore]:
    r.sql_fetchone = DataDir.sql_fetchone
    r.sql_fetchall = DataDir.sql_fetchall
    r.sql_execute = DataDir.sql_execute
    r.poke = DataDir.poke

class Accounts(DataDir):
    """ This is the account storage that stores account names,
        ids, full blockchain dump and a dict of balances
        in the `accounts` table in the SQLite3 database.
    """
    __tablename__ = 'accounts'
    __columns__ = [ 'id', 'account', 'account_id', 'graphene_json', 'balances_json', 'keys', 'comment' ]

    def __init__(self, *args, **kwargs):
        super(Accounts, self).__init__(*args, **kwargs)

    def create(self):
        """ Create the new table in the SQLite database
        """
        query = ('CREATE TABLE %s (' % self.__tablename__ +
                 'id INTEGER PRIMARY KEY AUTOINCREMENT,' +
                 'account STRING(256),' +
                 'account_id STRING(256),' +
                 'graphene_json TEXT,' +
                 'balances_json TEXT,' +
                 'keys INTEGER,'
                 'comment STRING(256)'
                 ')',)
        self.sql_execute(query)

    def upgrade(self):
        self.add_column('comment', 'STRING(256)')


    def getAccounts(self):
        """ Returns all account names stored in the database
        """
        query = ("SELECT account from %s WHERE keys > 0" % (self.__tablename__), )
        results = self.sql_fetchall(query)
        return [x[0] for x in results]

    def getContacts(self):
        """ Returns ALL accounts stored in the database
        """
        query = ("SELECT graphene_json, balances_json, account, account_id, keys, comment from %s " % (self.__tablename__), )
        results = self.sql_fetchall(query)
        ret = [ ]
        for row in results:
            body = json.loads(row[0])
            body.pop('_balances', None)
            body['balances'] = json.loads(row[1]) if row[1] else { }
            body['name'] = row[2]
            body['id'] = row[3]
            body['keys'] = int(row[4])
            body['comment'] = row[5]
            ret.append(body)
        return ret

    def getBy(self, key, some_id):
        """
        """
        if key not in ['account', 'account_id']:
            raise KeyError("'key' must be account or account_id")
        query = ("SELECT graphene_json, balances_json, account, account_id from %s " % (self.__tablename__) +
                 "WHERE %s=?" % (key),
                 (some_id, ))
        row = self.sql_fetchone(query)
        if not row:
            return None

        body = json.loads(row[0])
        body.pop('_balances', None)
        body['balances'] = json.loads(row[1]) if row[1] else { }
        body['name'] = row[2]
        body['id'] = row[3]
        return body

    def getById(self, account_id):
        return self.getBy('account_id', account_id)

    def getByName(self, account_name):
        return self.getBy('account', account_name)

    def update(self, account_name, key, val):
        """
        """
        if not(key in ['graphene_json','balances_json','keys','comment']):
            raise ValueError("'key' must be graphene_json, balances_json, keys or comment")
        if key == 'graphene_json':
           val.pop('balances', None)
           val.pop('_balances', None)
        if key.endswith('_json'):
           val = json.dumps(val)
        query = ("UPDATE %s " % self.__tablename__ +
                 ("SET %s=? WHERE account=?" % key),
                 (val, account_name))
        self.sql_execute(query)

    def add(self, account_name, account_id=None, keys=2):
        """ Add an account

           :param str account_name: Account name
        """
        if self.getByName(account_name):
            raise ValueError("Account already in storage")
        query = ('INSERT INTO %s (account, account_id, keys) ' % self.__tablename__ +
                 'VALUES (?, ?, ?)',
                 (account_name, account_id, keys, ))
        self.sql_execute(query)

    def delete(self, account_name):
        """ Delete the record identified as `account_name`

           :param str account_name: Account name
        """
        query = ("DELETE FROM %s " % (self.__tablename__) +
                 "WHERE account=?",
                 (account_name,))
        self.sql_execute(query)

    def wipe(self):
        """ Delete ALL entries
        """
        query = ("DELETE FROM %s " % (self.__tablename__),)
        self.sql_execute(query)



class Label(DataDir):
    """ This is the account storage that stores account names,
        and optional public keys (for cache sake)
        in the `accounts` table in the SQLite3 database.
    """
    __tablename__ = 'labels'

    def __init__(self, *args, **kwargs):
        super(Label, self).__init__(*args, **kwargs)

    def create(self):
        """ Create the new table in the SQLite database
        """
        query = ('CREATE TABLE %s (' % self.__tablename__ +
                 'id INTEGER PRIMARY KEY AUTOINCREMENT,' +
                 'label STRING(256),' +
                 'pub STRING(256)' +
                 ')', )
        self.sql_execute(query)

    def getLabels(self):
        """ Returns all labels stored in the database
        """
        query = ("SELECT label from %s " % (self.__tablename__))
        result = self.sql_fetchall(query)
        return [x[0] for x in results]

    def updateKey(self, label, pub):
        """ Change the wif to a pubkey

           :param str pub: Public key
           :param str wif: Private key
        """
        query = ("UPDATE %s " % self.__tablename__ +
                 "SET pub=? WHERE label=?",
                 (pub, label))
        self.sql_execute(query)

    def add(self, label, pub):
        """ Add an account

           :param str account_name: Account name
        """
        if self.getLabel(label):
            raise ValueError("Label already in storage")
        query = ('INSERT INTO %s (label, pub) ' % self.__tablename__ +
                 'VALUES (?, ?)',
                 (label, pub))
        self.sql_execute(query)

    def delete(self, label):
        """ Delete the record identified as `label`

           :param str label: Label
        """
        query = ("DELETE FROM %s " % (self.__tablename__) +
                 "WHERE label=?",
                 (label))
        self.sql_execute(query)



class History(DataDir):
    """ This is the account storage that stores account names,
        and optional public keys (for cache sake)
        in the `accounts` table in the SQLite3 database.
    """
    __tablename__ = 'history'
    __columns__ = [
        "id", "account", "description", "op_index",
        "operation", "memo", "block_num", "trx_in_block",
        "op_in_trx", "virtual_op", "trxid", "trxfull", "details", "date" ]

    def __init__(self, *args, **kwargs):
        super(History, self).__init__(*args, **kwargs)

    def create(self):
        """ Create the new table in the SQLite database
        """
        query = ('CREATE TABLE %s (' % self.__tablename__ +
                 'id INTEGER PRIMARY KEY AUTOINCREMENT,' +
                 'account STRING(256),' +
                 'description STRING(512),' +
                 'op_index STRING(256),' +

                 'operation TEXT,' +
                 'memo INTEGER,' +
                 'block_num INTEGER,' +
                 'trx_in_block INTEGER,' +
                 'op_in_trx INTEGER,' +
                 'virtual_op INTEGER,' +
                 'trxid STRING(256),' +
                 'trxfull TEXT,' +

                 'details TEXT,' +
                 'date TEXT'
                 ')', )
        self.sql_execute(query)

    def getEntries(self, account_name):
        """ Returns all entries stored in the database
        """
        query = (("SELECT * from %s " % self.__tablename__) +
            "WHERE account=? ORDER BY CAST(substr(op_index,6) as INTEGER) DESC ",
            (account_name,)
        )
        rows = self.sql_fetchall(query)
        return self.sql_todict(self.__columns__, rows)

    def getLastOperation(self, account_name):
        query = (("SELECT op_index from %s " % self.__tablename__) +
            "WHERE account=? ORDER BY CAST(substr(op_index,6) as INTEGER) DESC LIMIT 1",
            (account_name,)
        )
        op = self.sql_fetchone(query)
        if not op:
            return None
        return op[0]

    def getEntry(self, op_index, account_name):
        query = (("SELECT * from %s " % self.__tablename__) +
            "WHERE op_index=? AND account=?",
            (op_index,account_name,)
        )
        row = self.sql_fetchone(query)
        if not row:
            return None
        return self.sql_todict(self.__columns__, [row])[0]


    def updateEntryMemo(self, id, memo):
        """ Change the memo of an entry

           :param str id: Internal database ID
           :param str memo: Memo text
        """
        query = ("UPDATE %s " % self.__tablename__ +
                 "SET memo=? WHERE id=?",
                 (memo, id))
        self.sql_execute(query)

    def updateDate(self, op_index, date):
        """ Change the date of an entry

           :param str op_index
           :param str date
        """
        query = ("UPDATE %s " % self.__tablename__ +
                 "SET date=? WHERE op_index=?",
                 (date, op_index))
        self.sql_execute(query)


    def add(self, account, description,
            op_index, operation, memo,
            block_num, trx_in_block, op_in_trx, virtual_op,
            trxid, trxfull, details):
        """ Add an entry

           :param str account_name: Account name
           :param str description: Short description
        """
        if self.getEntry(op_index, account):
            raise ValueError("Entry already in storage")

        query = ('INSERT INTO %s (' % self.__tablename__ +
                'account, description,'+
                'op_index, operation, memo,'+
                'block_num, trx_in_block, op_in_trx, virtual_op,'+
                'trxid, trxfull, details, date'+
                ') '  +
           'VALUES (?,?,  ?,?,?,  ?,?,?,?,  ?,?,?,datetime(CURRENT_TIMESTAMP) )',
           (account, description,
            op_index, operation, memo,
            block_num, trx_in_block, op_in_trx, virtual_op,
            trxid, trxfull, details))
        self.sql_execute(query)

    def delete(self, id):
        """ Delete the record identified by `id`

           :param int id: Internal db id
        """
        query = ("DELETE FROM %s " % (self.__tablename__) +
                 "WHERE id=?",
                 (id))
        self.sql_execute(query)

    def wipe(self):
        """ Delete ALL entries
        """
        query = ("DELETE FROM %s " % (self.__tablename__),)
        self.sql_execute(query)


class ExternalHistory(DataDir):
    """ This table stores gateway bridges.
    """
    __tablename__ = 'payments'
    __columns__ = [
        "id", "account", "gateway", "ioflag",
        "inputcointype", "outputcointype", "outputaddress",
        "receipt_json", "remote_json", "coindata_json", "walletdata_json",
        "creationdate" ]

    def __init__(self, *args, **kwargs):
        super(ExternalHistory, self).__init__(*args, **kwargs)

    def create(self):
        """ Create the new table in the SQLite database
        """
        query = ('CREATE TABLE %s (' % self.__tablename__ +
                 'id INTEGER PRIMARY KEY AUTOINCREMENT,' +
                 'account STRING(256),' +
                 'gateway STRING(256),' +
                 'ioflag INTEGER,' +
                 'inputoutput INTEGER,' +
                 'inputcointype STRING(32),' +
                 'outputcointype STRING(32),' +
                 'outputaddress STRING(256),' +
                 'receipt_json TEXT,'+
                 'remote_json TEXT,' +
                 'coindata_json TEXT,' +
                 'walletdata_json TEXT,' +
                 'creationdate TEXT'
                 ')', )
        self.sql_execute(query)


    def getAllEntries(self):
        """ Returns all entries stored in the database
        """
        query = ("SELECT " +
            (",".join(self.__columns__)) +
            (" FROM %s " % self.__tablename__)
            ,
        )
        rows = self.sql_fetchall(query)
        return self.sql_todict(self.__columns__, rows)


    def getEntries(self, account_name):
        """ Returns all entries stored in the database
        """
        query = ("SELECT " +
            (",".join(self.__columns__)) +
            (" FROM %s " % self.__tablename__) +
            "WHERE account=?",
            (account_name,)
        )
        rows = self.sql_fetchall(query)
        return self.sql_todict(self.__columns__, rows)

    def getEntry(self, id, key="gatewayid"):
        if key not in self.__columns__:
            raise KeyError("Key %s not in columns" % key)
        query = ("SELECT " +
            (",".join(self.__columns__)) + 
            (" FROM %s " % self.__tablename__) +
            ("WHERE %s=? " % key),
            (id,)
        )
        row = self.sql_fetchone(query)
        return self.sql_todict(self.__columns__, [row])[0]

    def updateEntry(self, id, key, val):
        """ Change the memo of an entry

           :param str id: Internal db id 
           :param str key: Table filed to update
           :param str val: Value to set
        """
        if key not in self.__columns__:
            raise ValueError("%s not in columns" % key)
        query = ("UPDATE %s " % self.__tablename__ +
                 "SET %s=? WHERE id=?" % key ,
                 (val, id))
        self.sql_execute(query)

    def updateCoinData(self, gatewayName, coinType, coindata_json, walletdata_json):
        """ Change the memo of an entry

           :param str id: Internal db id 
           :param str key: Table filed to update
           :param str val: Value to set
        """
        #if key not in self.__columns__:
        #   raise ValueError("%s not in columns" % key)
        query = ("UPDATE %s " % self.__tablename__ +
                 "SET coindata_json=?, walletdata_json=? WHERE gateway=? AND inputcointype=?" ,
                 (coindata_json, walletdata_json,  gatewayName, coinType))
        self.sql_execute(query)

    def add(self, account, gateway, ioflag,
                 inputcointype, outputcointype, outputaddress,
                 receipt_json, coindata_json, walletdata_json):
        """ Add an entry
        """
        #if self.getEntry(gateway, gatewayid):
        #   raise ValueError("Entry already in storage")

        query = ('INSERT INTO %s (' % self.__tablename__ +
                 'account, gateway, ioflag, ' +
                 'inputcointype, outputcointype, outputaddress,' +
                 'receipt_json, coindata_json, walletdata_json, creationdate'
                 ') '  +
           'VALUES (?,?,?,  ?,?,?,  ?,?,?, datetime(CURRENT_TIMESTAMP) )',
           (account, gateway, ioflag,
                 inputcointype, outputcointype, outputaddress,
                 receipt_json, coindata_json, walletdata_json))
        id = self.sql_execute(query, lastid=True)
        return id

    def delete(self, id):
        """ Delete the record identified by `id`

           :param int id: Internal db id
        """
        query = ("DELETE FROM %s " % (self.__tablename__) +
                 "WHERE id=?",
                 (id, ))
        self.sql_execute(query)


class Remotes(DataDir):
    """
    """
    __tablename__ = 'remotes'
    __columns__ = [ 'id', 'label', 'url', 'refurl', 'rtype', 'ctype' ]

    RTYPE_BTS_NODE = 0
    RTYPE_BTS_GATEWAY = 1
    RTYPE_BTS_FAUCET = 2

    def __init__(self, *args, **kwargs):
        super(Remotes, self).__init__(*args, **kwargs)

    def create(self):
        """ Create the new table in the SQLite database
        """
        query = ('CREATE TABLE %s (' % self.__tablename__ +
                 'id INTEGER PRIMARY KEY AUTOINCREMENT,' +
                 'label STRING(256),' +
                 'url STRING(1024),' +
                 'refurl STRING(1024),' +
                 'rtype INTEGER,' +
                 'ctype STRING(256)' +
                 ')', )
        self.sql_execute(query)

    def upgrade(self):
        """ You must check if `table_exists()` before calling this. """
        if self.column_exists('refurl'): return

        query = ("DROP TABLE %s" % (self.__tablename__), ())
        self.sql_execute(query)
        self.create()
        import bitsharesqt.bootstrap as bootstrap
        for n in bootstrap.KnownFaucets:
            self.add(2, n[0], n[1], n[2], n[3].__name__)
        for n in bootstrap.KnownTraders:
            self.add(1, n[0], n[1], n[2], n[3].__name__)
        for n in bootstrap.KnownNodes:
            self.add(0, n[0], n[1], n[2], "")

        #self.add_column('refurl', 'STRING(1024)')
        #self.add_column('rtype', 'INTEGER')
        #self.add_column('ctype', 'STRING(256)')

    def getRemotes(self, rtype):
        """
        """
        query = ("SELECT " +
            (",".join(self.__columns__)) +
            (" FROM %s " % self.__tablename__) +
            "WHERE rtype=?",
            (rtype,)
        )
        rows = self.sql_fetchall(query)
        return self.sql_todict(self.__columns__, rows)

    def getById(self, id):
        """ Return single entry by internal database id
        """
        query = ("SELECT " +
            (",".join(self.__columns__)) +
            (" FROM %s " % self.__tablename__) +
            "WHERE id=?",
            (id,)
        )
        row = self.sql_fetchone(query)
        if not row: return None
        return self.sql_todict(self.__columns__, [row])[0]


    def add(self, rtype, label, url, refurl, ctype):
        """
        """
        query = ('INSERT INTO %s (label, url, refurl, ctype, rtype) ' % self.__tablename__ +
                 'VALUES (?, ?, ?, ?, ?)',
                 (label, url, refurl, ctype, rtype))
        return self.sql_execute(query, lastid=True)

    def update(self, id, key, val):
        """
            :param id internal db id
            :param key key to update
            :param val value
        """
        query = ('UPDATE %s SET %s = ? ' % (self.__tablename__, key) +
                 'WHERE id = ?',
                 (val, id))
        return self.sql_execute(query)

    def delete(self, id):
        """ Delete entry by internal database id
        """
        query = ("DELETE FROM %s " % (self.__tablename__) +
                 "WHERE id=?",
                 (id,))
        self.sql_execute(query)

    def wipe(self):
        """ Delete ALL entries
        """
        query = ("DELETE FROM %s " % (self.__tablename__),)
        self.sql_execute(query)


class Assets(DataDir):
    """ This is the asset storage that stores asset names,
        ids, issuer_ids, and related graphene json data
        in the `assets` table in the SQLite3 database.
    """
    __tablename__ = 'assets'
    __columns__ = [ 'id', 'symbol', 'asset_id', 'issuer_id',
        'graphene_json', 'favourite' ]

    def __init__(self, *args, **kwargs):
        super(Assets, self).__init__(*args, **kwargs)
        self.symbols_to_ids = { }
        self.ids_to_symbols = { }
        self.loaded_assets = { }

    def create(self):
        """ Create the new table in the SQLite database
        """
        query = ('CREATE TABLE %s (' % self.__tablename__ +
                 'id INTEGER PRIMARY KEY AUTOINCREMENT,' +
                 'symbol STRING(256),' +
                 'asset_id STRING(256),' +
                 'issuer_id STRING(256),' +
                 'graphene_json TEXT,' +
                 'favourite INTEGER DEFAULT 0'
                 ')', )
        self.sql_execute(query)

    def upgrade(self):
        self.add_column('favourite','INTEGER DEFAULT 0')

    def getAssets(self, invert_keys=None, favourite=None):
        """ Returns all assets cached in the database
            if `invert_keys` is None, returns a list of asset names
            if it is True, returns a dict of ids=>symbol mappings
            if it is False, returns a dict of symbol=>id mappings
        """
        extra = ""
        if not(favourite is None):
            extra += " WHERE favourite = %d " % (1 if favourite else 0)
        query = ("SELECT asset_id, symbol, graphene_json from %s " % (self.__tablename__) + extra)
        results = self.sql_fetchall(query)
        for result in results:
            id = result[0]
            sym = result[1]
            self.symbols_to_ids[sym] = id
            self.ids_to_symbols[id] = sym
            self.loaded_assets[id] = json.loads(result[3])

        if invert_keys == False:
            return self.symbols_to_ids

        if invert_keys == True:
            return self.ids_to_symbols

        return self.loaded_assets #symbols_to_ids.keys()

    def getAssetsLike(self, name, ordered=False, limit=None):
        """
        """
        extra = ""
        if ordered:
            extra += " ORDER BY symbol"
        if limit:
            extra += " LIMIT %d" % (limit)
        query = ("SELECT graphene_json FROM %s " % (self.__tablename__) +
                 "WHERE symbol LIKE ? OR symbol LIKE ?" + extra,
                (name+"%", "%."+name.replace('.',''),))
        results = self.sql_fetchall(query)
        return [x[0] for x in results]

    def getByIssuer(self, issuer_id):
        """
        """
        query = ("SELECT graphene_json FROM %s " % (self.__tablename__) +
                 "WHERE issuer_id = ?",
                (issuer_id, ))
        results = self.sql_fetchall(query)
        return [x[0] for x in results]

    def getBySymbol(self, symbol):
        """
        """
        symbol = symbol.upper()
        return self.getById(symbol, is_symbol=True)

    def getById(self, asset_id, is_symbol=False):
        """
        """
        if is_symbol:
            if asset_id in self.symbols_to_ids:
                asset_id = self.symbols_to_ids[asset_id]
                is_symbol = False

        if not is_symbol:
            if asset_id in self.loaded_assets:
                return self.loaded_assets[asset_id]

        query = ("SELECT graphene_json from %s " % (self.__tablename__) +
                 "WHERE %s=?" % ("symbol" if is_symbol else "asset_id"),
                 (asset_id, ))
        row = self.sql_fetchone(query)
        if not row:
            return None

        body = json.loads(row[0])
        sym = body["symbol"]
        asset_id = id = body["id"]
        self.symbols_to_ids[sym] = id
        self.ids_to_symbols[id] = sym
        self.loaded_assets[asset_id] = body
        return body

    def add(self, asset_id, symbol, graphene_json):
        """ Add an asset

           :param str asset_id: Asset ID (1.3.X)
           :param str symbol: Asset Symbol
           :param dict graphene_json: Dump from blockchain
        """
        if self.getById(asset_id):
            raise ValueError("Asset already in storage")
        if not('issuer' in graphene_json):
            raise KeyError("Missing issuer key")
        issuer_id = graphene_json['issuer']
        query = ('INSERT INTO %s (symbol, asset_id, issuer_id, graphene_json) ' % self.__tablename__ +
                 'VALUES (?, ?, ?, ?)',
                 (symbol.upper(), asset_id, issuer_id, json.dumps(graphene_json)))
        self.sql_execute(query)

    def countEntries(self):
        return len(self) # invoke __len__

    def update(self, asset_id, graphene_json):
        """ Update an asset

           :param dict graphene_json: New asset data
        """
        query = ('UPDATE %s SET graphene_json = ? ' % self.__tablename__ +
                 'WHERE asset_id = ?',
                 (json.dumps(graphene_json), asset_id))
        self.sql_execute(query)
        self.loaded_assets[asset_id] = graphene_json

    def set_favourite(self, asset_id, fav=True):
        """ Update an asset

           :param str asset_id: Asset ID ('1.2.0')
           :param bool fav: Is user favourite
        """
        query = ('UPDATE %s SET favourite = ? ' % self.__tablename__ +
                 'WHERE asset_id = ?',
                 ((1 if fav else 0), asset_id))
        self.sql_execute(query)

    def deleteBySymbol(self, symbol):
        """ Delete the record identified as `symbol`

           :param str symbol: Asset Symbol ('bts')
        """
        return self.deleteById(symbol, is_symbol=True)

    def deleteById(self, asset_id, is_symbol=False):
        """ Delete the record identified as `asset_id`

           :param str asset_id: Asset ID ('1.2.0')
        """
        if is_symbol:
            if asset_id in self.symbols_to_ids:
                asset_id = self.symbols_to_ids[asset_id]
                is_symbol = False

        self.sql_execute(
            "DELETE FROM %s " % (self.__tablename__) +
            "WHERE %s=?" ("symbol" if is_symbol else "asset_id"),
            (asset_id, )
        )
        if asset_id in self.loaded_assets:
            self.loaded_assets.pop(asset_id)

    def wipe(self):
        """ Delete ALL entries
        """
        query = ("DELETE FROM %s " % (self.__tablename__),)
        self.sql_execute(query)
        self.loaded_assets = { }

class BlindAccounts(DataDir):
    """
    """
    __tablename__ = 'blindaccounts'
    __columns__ = [ 'id', 'label', 'pub', 'graphene_json', 'balances_json',
         'keys' ]

    def __init__(self, *args, **kwargs):
        super(BlindAccounts, self).__init__(*args, **kwargs)

    def create(self):
        """ Create the new table in the SQLite database
        """
        query = ('CREATE TABLE %s (' % self.__tablename__ +
                 'id INTEGER PRIMARY KEY AUTOINCREMENT,' +
                 'label STRING(256),' +
                 'pub STRING(256),' +
                 'graphene_json TEXT,' +
                 'balances_json TEXT,' +
                 'keys INTEGER'
                 ')', )
        self.sql_execute(query)

    def upgrade(self):
        self.add_column('keys','INTEGER DEFAULT 1')

    def getAccounts(self):
        """ Returns all blind accounts stored in the database
        """
        query = ("SELECT label, pub from %s WHERE keys > 0" % (self.__tablename__), )
        results = self.sql_fetchall(query)
        return results

    def getContacts(self):
        """ Returns ALL blind accounts (and contacts)
        """
        query = ("SELECT label, pub, keys from %s" % (self.__tablename__), )
        rows = self.sql_fetchall(query)
        return self.sql_todict(['label','pub','keys'], rows)

    def getBy(self, key, some_id):
        """
        """
        if key not in ['label', 'pub']:
            raise KeyError("'key' must be label or pub")
        query = ("SELECT graphene_json, balances_json, label, pub, keys from %s " % (self.__tablename__) +
                 "WHERE %s=?" % (key),
                 (some_id, ))
        row = self.sql_fetchone(query)
        if not row:
            return None

        query = ("SELECT " +
            (",".join(self.__columns__)) +
            (" FROM %s " % self.__tablename__)
            ,
        )

        body = json.loads(row[0]) if row[0] else { }
        body['balances'] = json.loads(row[1]) if row[1] else { }
        body['label'] = row[2]
        body['pub'] = row[3]
        body['keys'] = row[4]
        return body

    def getByPublicKey(self, pub):
        return self.getBy('pub', str(pub))

    def getByLabel(self, label):
        return self.getBy('label', label)

    def update(self, pub, key, val):
        """ Update blind account identified by `pub`lic key

           :param str pub: Public key
           :param str key: label, graphene_json or balances_json
           :param val: value to set
        """
        if not(key in ['label', 'graphene_json', 'balances_json', 'keys']):
            raise ValueError("'key' must be graphene_json, balances_json, label or keys")
        if key.endswith('_json'):
           val = json.dumps(val)
        if key == 'keys':
           val = int(val)
        if key == 'label':
           val = str(val)
           if not val.strip():
               raise ValueError("Label can not be empty")
           if val.startswith("BTS"):
               raise ValueError("Label can not begin with letters 'BTS'")
           if self.getByLabel(val):
               raise ValueError("Label already in use")

        query = ("UPDATE %s " % self.__tablename__ +
                 ("SET %s=? WHERE pub=?" % key),
                 (val, pub))
        self.sql_execute(query)

    def add(self, pub, label, keys=1):
        """ Add a blind account

           :param str pub: Public key
           :param str label: Account name
           :param int keys: Number of keys
        """
        if not label.strip():
            raise ValueError("Label can not be empty")
        if label.startswith("BTS"):
            raise ValueError("Label can not begin with letters 'BTS'")
        if self.getByLabel(label):
            raise ValueError("Label already in use")
        if self.getByPublicKey(pub):
            raise ValueError("Account already in storage")

        query = ('INSERT INTO %s (pub, label, keys) ' % self.__tablename__ +
                 'VALUES (?, ?, ?)',
                 (pub, label, keys))
        self.sql_execute(query)

    def delete(self, pub):
        """ Delete the record identified by `pub`lic key

           :param str pub: Public key
        """
        query = ("DELETE FROM %s " % (self.__tablename__) +
                 "WHERE pub=?",
                 (pub,))
        self.sql_execute(query)



#from bitshares.storage import BlindAccounts, BlindHistory
#from bitshares.storage import CommonStorage

class BitsharesStorageExtra():#CommonStorage):

    def __init__(self, path, create=True, **kwargs):
        log.info("Initializing storage %s create: %s" %(path, str(create)))
        #super(BitsharesStorageExtra, self).__init__(path=path, create=create, **kwargs)

        # Bitshares
        self.configStorage = SqliteConfigurationStore(path=path, create=create)
        self.keyStorage = SqliteEncryptedKeyStore(config=self.configStorage, path=path, create=create)
        self.blindStorage = SqliteBlindHistoryStore(path=path, create=create)

        # Extra storages
        self.accountStorage = Accounts(path=path, create=create)
        self.blindAccountStorage = BlindAccounts(path=path, create=create)
        #self.labelStorage = Label(path, create=create)
        self.assetStorage = Assets(path=path, create=create)
        self.historyStorage = History(path=path, create=create)
        self.remotesStorage = Remotes(path=path, create=create)
        self.gatewayStorage = ExternalHistory(path=path, create=create)

        # Set latest db version
        #self.configStorage["db_version"] = "3"
        from bitsharesextra.chatstorage import ChatRooms
        self.chatroomStorage = ChatRooms(path=path, create=create)

    def wipeConfig(self):
        config = self.configStorage
        masterPwd = self.keyStorage
        """ Wipe the store (different from `super().wipe()`)
        """
        query = ("DELETE FROM {} WHERE key <> ?".format(config.__tablename__),
            (masterPwd.config_key, )
        )
        config.sql_execute(query)

    def privateKeyExists(self, pub):
        keys = self.keyStorage
        query = ("SELECT COUNT(id) FROM {} WHERE pub = ?".format(keys.__tablename__),
            (pub, )
        )
        return int(keys.sql_fetchone(query)[0])

    def countPrivateKeys(self, pubs):
        total = 0
        for pub in pubs:
            total += self.privateKeyExists(pub)
        return total
