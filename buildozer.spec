[app]
title = E.D.I
package.name = edi
package.domain = org.edi
source.dir = .
source.include_exts = py,png,jpg,jpeg,gif,txt,json
version = 1.0.0
requirements = python3,kivy,google-generativeai,grpcio,protobuf,requests,websockets,Pillow,numpy,psutil

# p4a branch
p4a.branch = develop
orientation = portrait
osx.python_version = 3
osx.kivy_version = 2.2.0
fullscreen = 0

# Permissions
android.permissions = RECORD_AUDIO,INTERNET,MODIFY_AUDIO_SETTINGS

# API level
android.api = 33
android.minapi = 26
android.ndk = 27b

# Presplash
android.presplash_color = #00060a

# Icon
android.icon = icon.png

# Architectures
android.archs = arm64-v8a

# Log level
android.logcat_filters =

# Debug
android.debug = 1

# Accept SDK license
android.accept_sdk_license = yes

# Fresh SDK download
android.sdk_manager = sdkmanager

[buildozer]
log_level = 2
warn_on_root = 1

[services]

[app:arm64-v8a]
