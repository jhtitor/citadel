# -*- mode: python -*-
import os
import sys
sys.path += [ os.path.abspath(SPECPATH) ]
import bitsharesqt.version as version

EXE_NAME=version.UNIX_NAME

def bundle_version_file():
    verfile = os.path.abspath(os.path.join(SPECPATH, "version.txt"))
    with open(verfile, "w") as f:
        f.write(version.git_version(version.VERSION))

bundle_version_file()

import platform
def is_os_64bit():
    return platform.machine().endswith('64')


binaries = [ ]
hidden_imports = [ ]

def download_file(filename, url):
    if not(os.path.isfile(filename)):
        import requests
        print("Downloading", url)
        response = requests.get(url)
        try:
            html = response.text.startswith('<!DOCTYPE html>')
        except:
            html = False
        if html:
            raise Exception("Download error (some HTML is on the way)")
        with open(filename, "wb") as f:
            f.write(response.content)
    return filename
def extract_file(archive, name):
    import zipfile
    with zipfile.ZipFile(archive, "r") as zip:
        zip.extract(name)

def download_windows_openssl(i686=True):
    if i686:
        filename = 'openssl-1.0.2o-i386-win32.zip'
    else:
        filename = 'openssl-1.0.2o-x64_86-win64.zip'
    # Picked from https://wiki.openssl.org/index.php/Binaries
    url = 'https://indy.fulgan.com/SSL/' + filename
    return download_file(filename, url)

if sys.platform == 'win32':
    EXE_NAME=version.BUNDLE_NAME

    i686 = not(is_os_64bit())
    archive = download_windows_openssl( i686 )
    #if i686:
    dlls = [ 'libeay32.dll', 'ssleay32.dll' ]
    for dll in dlls:
        extract_file(archive, dll)
    #    binaries.append( (dll, '.') )
    #else:
    #    pass
    import ntpath
    import imp
    dll = imp.find_module('_scrypt')[1]
    #binaries.append( (dll, '.') )
    #
    # NOTE: instead of adding to binaries, we just
    # provide "hidden_imports: _scrypt" below
    hidden_imports.append( '_scrypt' )

if sys.platform == "darwin":
    hidden_imports.append( '_scrypt' )

# For PyQt5 >= 5.11, and pyinstaller not yet patched, we add this:
hidden_imports.append("PyQt5.sip")

datas=[('version.txt', '.')]

mgc_paths=['/opt/local/share/misc', # macports
'/usr/lib/file', '/usr/share/file', '/usr/local/share/file']
for path in mgc_paths:
	p = os.path.join(path, "magic.mgc")
	if os.path.isfile(p):
		datas.append( (p, '.') )
		break
print("DATAS:", datas)
block_cipher = None

a = Analysis(['citadel'],
             pathex=[ ],
             binaries=binaries,
             datas=datas,#[('version.txt', '.')],
             hiddenimports=hidden_imports,
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name=EXE_NAME,
          debug=False,
          strip=False,
          upx=True,
          runtime_tmpdir=None,
          console=False,
          icon='images/app.ico')

#coll = COLLECT(exe,
#               a.binaries,
#               a.zipfiles,
#               a.datas,
#               strip=False,
#               upx=True,
#               name='main')

app = BUNDLE(exe,
         name=version.BUNDLE_NAME+'.app',
         icon='build/app.icns',
         bundle_identifier=None,
         info_plist={
                "CFBundleName": version.BUNDLE_NAME,
                "CFBundleDisplayName": version.SHORT_DESCRIPTION,
                "CFBundleIdentifier": "li.citadel.desktop",
                "CFBundleShortVersionString": version.VERSION,
                "NSPrincipalClass": "NSApplication",
                "NSHighResolutionCapable": True,
        }
)

