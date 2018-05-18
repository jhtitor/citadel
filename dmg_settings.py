BUNDLE_NAME="BitShares-QT"
BUNDLE_NAME="Citadel"

APP=BUNDLE_NAME+".app"

files = [ 'dist/' + APP ]
symlinks = { 'Applications': '/Applications' }

icon = 'dist/' + APP + '/Contents/Resources/app.icns'
badge_icon = 'dist/' + APP + '/Contents/Resources/app.icns'
icon_locations = {
               APP: (100, 100),
    'Applications': (500, 100)
}

background = 'builtin-arrow'
background = 'images/dmg_background.png'
