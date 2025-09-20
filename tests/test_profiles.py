from calibration_loader.profiles import load_profile


def test_load_audiocalib_profile(tmp_path):
    profile = load_profile('data/DELL_C2723H__HD_Audio_Driver_for_Display_Audio__portaudio-11.json')
    assert profile['device']['wasapi_id'] == 'portaudio-11'
    assert profile['schema'] == 'audiocalib.v1'
    # Controlla che i canali siano normalizzati e negativi
    assert profile['channels']['OS'][125] == -10.0
    assert profile['channels']['OD'][500] == -5.0
    # Hash deve essere stabile
    another = load_profile('data/DELL_C2723H__HD_Audio_Driver_for_Display_Audio__portaudio-11.json')
    assert profile == another
