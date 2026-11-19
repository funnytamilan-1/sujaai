# SUJAAI Flutter app
This folder contains the Flutter + Dart mobile client, connected to the existing FastAPI backend.

## Google OAuth configuration
1. Create a Google OAuth Web client ID and an Android OAuth client in Google Cloud Console.
2. Set backend environment variable GOOGLE_CLIENT_ID to the Web client ID.
3. Configure the Android OAuth client with the package name and signing SHA-1.
4. Supply the same Web client ID as GOOGLE_SERVER_CLIENT_ID to Flutter.
5. Set API_BASE_URL to the backend API prefix, e.g. https://api.example.com/api.

Google sign-in is verified by the backend and restricted to the configured administrator email. It does not create public accounts.

## Run
```sh
cd mobile
flutter create --platforms android --project-name sujaai_mobile .
flutter pub get
flutter run --dart-define=API_BASE_URL=https://YOUR_API_HOST/api --dart-define=GOOGLE_SERVER_CLIENT_ID=YOUR_WEB_CLIENT_ID
```
For an Android emulator, the default API base is http://10.0.2.2:8000/api.

## Build APK
```sh
flutter build apk --release --dart-define=API_BASE_URL=https://YOUR_API_HOST/api --dart-define=GOOGLE_SERVER_CLIENT_ID=YOUR_WEB_CLIENT_ID
```
