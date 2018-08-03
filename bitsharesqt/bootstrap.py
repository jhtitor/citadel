from rpcs.blocktradesus import BlockTradesUS
from rpcs.winexpro import WinexPRO
from rpcs.rudexorg import RuDexORG
from rpcs.xbtsio import XBtsIO
from rpcs.btsfaucet import BTSFaucet

KnownNodes = [
	('Bitshares EU', 'wss://node.bitshares.eu', ''),
	('DacPlay', 'wss://bitshares.dacplay.org:8089/ws', ''),
	('OpenLedger.info', 'wss://bitshares.openledger.info/ws', ''),
	('OpenLedger EU', 'wss://eu.openledger.info/ws', ''),
	('OpenLedger HK', 'wss://openledger.hk/ws', ''),
	('Dele-Puppy', 'wss://dele-puppy.com/ws', ''),
	('RNGlab', 'https://dex.rnglab.org/', ''),
	('Citadel', 'wss://citadel.li/node', ''),
	('Citadel (TOR)', 'ws://citadel2miawoaqw.onion/node/ws', ''),
	('GDex', 'wss://ws.gdex.top/', ''),
	('Crypto.Fans', 'wss://bitshares.crypto.fans/ws', ''),
	('BTSABC', 'wss://bit.btsabc.org/ws', ''),
	('DexNode', 'wss://dexnode.net/ws', ''),
	('DexNode LA', 'wss://la.dexnode.net/ws', ''),
	('blkchnd', 'wss://api.bts.blckchnd.com/', ''),
	('AI.LA', 'wss://bts.ai.la/ws', ''),
	('XelDal', 'wss://kc-us-dex.xeldal.com/ws', ''),
	('WanCloud', 'wss://bitshares-api.wancloud.io/ws', ''),
	('ApAsia', 'wss://bitshares.apasia.tech/ws', ''),
	('ApAsia JP', 'wss://japan.bitshares.apasia.tech/ws', ''),
#	('localhost', 'ws://localhost:8090', ''),
]

KnownTraders = [
	('BlockTrades', 'https://api.blocktrades.us/v2/', 'https://wallet.bitshares.org', BlockTradesUS),
	('OpenLedger', 'https://ol-api1.openledger.info/api/v0/ol/support/', 'https://wallet.bitshares.org', BlockTradesUS),
	('CryptoBridge', 'https://ol-api1.openledger.info/api/v0/ol/support/', '', BlockTradesUS),
	('Citadel', 'https://citadel.li/trade/', '', BlockTradesUS),
	('Citadel (TOR)', 'http://citadel2miawoaqw.onion/trade/', '', BlockTradesUS),
	('Crypto-Bridge (unsupported)', 'https://api.crypto-bridge.org/api/v1/', 'https://wallet.crypto-bridge.org', BlockTradesUS),
	('Winex', 'https://gateway.winex.pro/api/v0/ol/support/', 'https://exchange.winex.pro', WinexPRO),
	('RuDEX', 'https://gateway.rudex.org/api/v0_1/', 'https://wallet.rudex.org', RuDexORG),
	('XBTSX', 'https://apis.xbts.io/api/v1/','https://ex.xbts.io/', XBtsIO)
#	('localhost', 'http://localhost:8011', '', BlockTradesUS),
]

KnownFaucets = [
	('Citadel', 'https://citadel.li/faucet/', '', BTSFaucet),
	('Citadel (TOR)', 'http://citadel2miawoaqw.onion/faucet/', '', BTSFaucet),
	('OpenLedger', 'https://bitshares.openledger.info', 'https://wallet.bitshares.org', BTSFaucet),
	('RuDEX', 'https://faucet.rudex.org', 'https://market.rudex.org', BTSFaucet),
	('DacPlay', 'https://bts2faucet.dacplay.org/', 'https://bitshares.dacplay.org', BTSFaucet),
	('CryptoBridge (wrong url?)', 'https://faucet.crypto-bridge.org/', 'https://wallet.crypto-bridge.org', BTSFaucet),
	('Winex', 'https://faucet.winex.pro/api/v1/accounts', 'https://exchange.winex.pro/', BTSFaucet)
#	('localhost', 'http://localhost:8012', '', BTSFaucet),
]

CoreAsset = {
	"options": {
		"max_market_fee": "1000000000000000",
		"core_exchange_rate": {
			"base": {
				"amount": 1, "asset_id": "1.3.0"
			},
			"quote": {
				"amount": 1, "asset_id": "1.3.0"
			}
		},
		"whitelist_authorities": [ ],
		"blacklist_markets": [ ],
		"flags": 0,
		"market_fee_percent": 0,
		"issuer_permissions": 0,
		"description": "",
		"extensions": [ ],
		"whitelist_markets": [ ],
		"blacklist_authorities": [ ],
		"max_supply": "360057050210207"
	},
	"symbol": "BTS",
	"dynamic_asset_data_id": "2.3.0",
	"issuer": "1.2.3",
	"precision": 5,
	"id": "1.3.0"
}
