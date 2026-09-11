import 'package:flutter_test/flutter_test.dart';
import 'package:home_guard_app/services/device_id.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('mints a uuid once and reuses it', () async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    final first = await initDeviceId(prefs: prefs);
    expect(first, hasLength(36));
    expect(await initDeviceId(prefs: prefs), first);
    expect(prefs.getString(kDeviceIdKey), first);
  });

  test('keeps an id another sibling-shaped install already stored', () async {
    SharedPreferences.setMockInitialValues({kDeviceIdKey: 'existing-id'});
    final prefs = await SharedPreferences.getInstance();
    expect(await initDeviceId(prefs: prefs), 'existing-id');
  });

  test('opens the default prefs when none are injected', () async {
    SharedPreferences.setMockInitialValues({kDeviceIdKey: 'from-prefs'});
    expect(await initDeviceId(), 'from-prefs');
  });

  test('replaces an empty stored id', () async {
    SharedPreferences.setMockInitialValues({kDeviceIdKey: ''});
    final prefs = await SharedPreferences.getInstance();
    expect(await initDeviceId(prefs: prefs), isNot(isEmpty));
  });
}
