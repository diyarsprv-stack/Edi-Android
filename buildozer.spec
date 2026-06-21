[app]
title = E.D.I
package.name = edi
package.domain = org.edi
source.dir = .
source.include_exts = py,png,jpg,jpeg,gif,txt,json
version = 1.0.0
requirements = python3,kivy,google-generativeai,grpcio,protobuf,requests,websockets,pillow,psutil,numpy,pyjnius,android
orientation = portrait
osx.python_version = 3
osx.kivy_version = 2.2.0
fullscreen = 0

# Permissions
android.permissions = RECORD_AUDIO,INTERNET,MODIFY_AUDIO_SETTINGS

# API level
android.api = 33
android.minapi = 26
android.sdk = 34
android.ndk = 25b

# Presplash
android.presplash_color = #00060a

# Icon
android.icon = icon.png

# Architectures
android.archs = arm64-v8a

# Log level
android.logcat_filters =

# Debug
android.debug = 0

[buildozer]
log_level = 2
warn_on_root = 1

[services]

[app:arm64-v8a]
