# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later


import logging

import pytest

from qutebrowser.config import configdata
from qutebrowser.utils import usertypes, version, utils
from qutebrowser.browser.webengine import darkmode
from qutebrowser.misc import objects


@pytest.fixture(autouse=True)
def patch_backend(monkeypatch):
    monkeypatch.setattr(objects, 'backend', usertypes.Backend.QtWebEngine)


@pytest.fixture
def gentoo_versions():
    return version.WebEngineVersions(
        webengine=utils.VersionNumber(5, 15, 2),
        chromium='87.0.4280.144',
        source='faked',
    )


@pytest.mark.parametrize('value, webengine_version, expected', [
    # Auto
    ("auto", "5.15.2", [("preferredColorScheme", "2")]),  # QTBUG-89753
    ("auto", "5.15.3", []),
    ("auto", "6.2.0", []),
    ("auto", "6.6.0", []),

    # Unset
    (None, "5.15.2", [("preferredColorScheme", "2")]),  # QTBUG-89753
    (None, "5.15.3", []),
    (None, "6.2.0", []),
    (None, "6.6.0", []),

    # Dark
    ("dark", "5.15.2", [("preferredColorScheme", "1")]),
    ("dark", "5.15.3", [("preferredColorScheme", "0")]),
    ("dark", "6.2.0", [("preferredColorScheme", "0")]),
    ("dark", "6.6.0", [("preferredColorScheme", "0")]),

    # Light
    ("light", "5.15.2", [("preferredColorScheme", "2")]),
    ("light", "5.15.3", [("preferredColorScheme", "1")]),
    ("light", "6.2.0", [("preferredColorScheme", "1")]),
    ("light", "6.6.0", [("preferredColorScheme", "1")]),
])
def test_colorscheme(config_stub, value, webengine_version, expected):
    versions = version.WebEngineVersions.from_pyqt(webengine_version)
    if value is not None:
        config_stub.val.colors.webpage.preferred_color_scheme = value

    darkmode_settings = darkmode.settings(versions=versions, special_flags=[])
    assert darkmode_settings['blink-settings'] == expected


def test_colorscheme_gentoo_workaround(config_stub, gentoo_versions):
    config_stub.val.colors.webpage.preferred_color_scheme = "dark"
    darkmode_settings = darkmode.settings(versions=gentoo_versions, special_flags=[])
    assert darkmode_settings['blink-settings'] == [("preferredColorScheme", "0")]


@pytest.mark.parametrize('settings, expected', [
    # Disabled
    ({}, [('preferredColorScheme', '2')]),

    # Enabled without customization
    (
        {'enabled': True},
        [
            ('preferredColorScheme', '2'),
            ('forceDarkModeEnabled', 'true'),
            ('forceDarkModeImagePolicy', '2'),
        ]
    ),

    # Algorithm
    (
        {'enabled': True, 'algorithm': 'brightness-rgb'},
        [
            ('preferredColorScheme', '2'),
            ('forceDarkModeEnabled', 'true'),
            ('forceDarkModeInversionAlgorithm', '2'),
            ('forceDarkModeImagePolicy', '2'),
        ],
    ),
])
def test_basics(config_stub, settings, expected):
    for k, v in settings.items():
        config_stub.set_obj('colors.webpage.darkmode.' + k, v)

    # Using Qt 5.15.2 because it has the least special cases.
    versions = version.WebEngineVersions.from_pyqt('5.15.2')
    darkmode_settings = darkmode.settings(versions=versions, special_flags=[])
    assert darkmode_settings['blink-settings'] == expected


QT_515_2_SETTINGS = {'blink-settings': [
    ('preferredColorScheme', '2'),  # QTBUG-89753
    ('forceDarkModeEnabled', 'true'),
    ('forceDarkModeInversionAlgorithm', '2'),
    ('forceDarkModeImagePolicy', '2'),
    ('forceDarkModeTextBrightnessThreshold', '100'),
]}


QT_515_3_SETTINGS = {
    'blink-settings': [('forceDarkModeEnabled', 'true')],
    'dark-mode-settings': [
        ('InversionAlgorithm', '1'),
        ('ImagePolicy', '2'),
        ('TextBrightnessThreshold', '100'),
    ],
}

QT_64_SETTINGS = {
    'blink-settings': [('forceDarkModeEnabled', 'true')],
    'dark-mode-settings': [
        ('InversionAlgorithm', '1'),
        ('ImagePolicy', '2'),
        ('ForegroundBrightnessThreshold', '100'),
    ],
}

QT_66_SETTINGS = {
    'blink-settings': [('forceDarkModeEnabled', 'true')],
    'dark-mode-settings': [
        ('InversionAlgorithm', '1'),
        ('ImagePolicy', '2'),
        ('ForegroundBrightnessThreshold', '100'),
        ('ImageClassifierPolicy', '0'),  # kTransferable (default ML-based)
    ],
}


@pytest.mark.parametrize('qversion, expected', [
    ('5.15.2', QT_515_2_SETTINGS),
    ('5.15.3', QT_515_3_SETTINGS),
    ('6.4', QT_64_SETTINGS),
    ('6.6', QT_66_SETTINGS),
])
def test_qt_version_differences(config_stub, qversion, expected):
    settings = {
        'enabled': True,
        'algorithm': 'brightness-rgb',
        'threshold.foreground': 100,
    }
    for k, v in settings.items():
        config_stub.set_obj('colors.webpage.darkmode.' + k, v)

    versions = version.WebEngineVersions.from_pyqt(qversion)
    darkmode_settings = darkmode.settings(versions=versions, special_flags=[])
    assert darkmode_settings == expected


@pytest.mark.parametrize('setting, value, exp_key, exp_val', [
    ('contrast', -0.5,
     'Contrast', '-0.5'),
    ('policy.page', 'smart',
     'PagePolicy', '1'),
    ('policy.images', 'smart',
     'ImagePolicy', '2'),
    ('policy.images', 'smart-simple',
     'ImagePolicy', '2'),
    ('threshold.foreground', 100,
     'TextBrightnessThreshold', '100'),
    ('threshold.background', 100,
     'BackgroundBrightnessThreshold', '100'),
])
def test_customization(config_stub, setting, value, exp_key, exp_val):
    config_stub.val.colors.webpage.darkmode.enabled = True
    config_stub.set_obj('colors.webpage.darkmode.' + setting, value)

    expected = [
        ('preferredColorScheme', '2'),
        ('forceDarkModeEnabled', 'true'),
    ]
    if exp_key != 'ImagePolicy':
        expected.append(('forceDarkModeImagePolicy', '2'))
    expected.append(('forceDarkMode' + exp_key, exp_val))

    versions = version.WebEngineVersions.from_pyqt('5.15.2')
    darkmode_settings = darkmode.settings(versions=versions, special_flags=[])
    assert darkmode_settings['blink-settings'] == expected


@pytest.mark.parametrize('webengine_version, expected', [
    ('5.15.2', darkmode.Variant.qt_515_2),
    ('5.15.3', darkmode.Variant.qt_515_3),
    ('6.2.0', darkmode.Variant.qt_515_3),
    ('6.4.0', darkmode.Variant.qt_64),
    ('6.5.0', darkmode.Variant.qt_64),
    ('6.6.0', darkmode.Variant.qt_66),
    ('6.7.0', darkmode.Variant.qt_66),
])
def test_variant(webengine_version, expected):
    versions = version.WebEngineVersions.from_pyqt(webengine_version)
    assert darkmode._variant(versions) == expected


def test_variant_gentoo_workaround(gentoo_versions):
    assert darkmode._variant(gentoo_versions) == darkmode.Variant.qt_515_3


@pytest.mark.parametrize('value, is_valid, expected', [
    ('invalid_value', False, darkmode.Variant.qt_515_3),
    ('qt_515_2', True, darkmode.Variant.qt_515_2),
])
def test_variant_override(monkeypatch, caplog, value, is_valid, expected):
    versions = version.WebEngineVersions.from_pyqt('5.15.3')
    monkeypatch.setenv('QUTE_DARKMODE_VARIANT', value)

    with caplog.at_level(logging.WARNING):
        assert darkmode._variant(versions) == expected

    log_msg = 'Ignoring invalid QUTE_DARKMODE_VARIANT=invalid_value'
    assert (log_msg in caplog.messages) != is_valid


@pytest.mark.parametrize('flag, expected', [
    ('--blink-settings=key=value', [('key', 'value')]),
    ('--blink-settings=key=equal=rights', [('key', 'equal=rights')]),
    ('--blink-settings=one=1,two=2', [('one', '1'), ('two', '2')]),
    ('--enable-features=feat', []),
])
def test_pass_through_existing_settings(config_stub, flag, expected):
    config_stub.val.colors.webpage.darkmode.enabled = True
    versions = version.WebEngineVersions.from_pyqt('5.15.2')
    settings = darkmode.settings(versions=versions, special_flags=[flag])

    dark_mode_expected = [
        ('preferredColorScheme', '2'),
        ('forceDarkModeEnabled', 'true'),
        ('forceDarkModeImagePolicy', '2'),
    ]
    assert settings['blink-settings'] == expected + dark_mode_expected


@pytest.mark.parametrize('qversion, image_policy, expected_classifier_policy', [
    # Qt 6.6+: should have ImageClassifierPolicy setting
    ('6.6.0', 'smart', '0'),  # kTransferable (ML-based)
    ('6.6.0', 'smart-simple', '1'),  # kSimple (non-ML)
    # Qt <6.6: should not have ImageClassifierPolicy setting
    ('6.4.0', 'smart', None),
    ('6.4.0', 'smart-simple', None),
    ('5.15.3', 'smart', None),
    ('5.15.3', 'smart-simple', None),
])
def test_image_classifier_policy(config_stub, qversion, image_policy, expected_classifier_policy):
    """Test ImageClassifierPolicy setting behavior across Qt versions."""
    config_stub.val.colors.webpage.darkmode.enabled = True
    config_stub.val.colors.webpage.darkmode.policy.images = image_policy

    versions = version.WebEngineVersions.from_pyqt(qversion)
    darkmode_settings = darkmode.settings(versions=versions, special_flags=[])

    # Check if ImageClassifierPolicy is present in the settings
    dark_mode_settings = darkmode_settings.get('dark-mode-settings', [])
    classifier_policies = [setting for setting in dark_mode_settings if setting[0] == 'ImageClassifierPolicy']

    if expected_classifier_policy is None:
        assert len(classifier_policies) == 0, f"Expected no ImageClassifierPolicy for Qt {qversion}"
    else:
        assert len(classifier_policies) == 1, f"Expected exactly one ImageClassifierPolicy for Qt {qversion}"
        assert classifier_policies[0][1] == expected_classifier_policy


@pytest.mark.parametrize('qversion, image_policy', [
    # Test that both 'smart' and 'smart-simple' behave identically on older Qt versions
    ('6.4.0', 'smart'),
    ('6.4.0', 'smart-simple'),
    ('5.15.3', 'smart'),
    ('5.15.3', 'smart-simple'),
])
def test_image_policy_compatibility(config_stub, qversion, image_policy):
    """Test that 'smart' and 'smart-simple' behave identically on older Qt versions."""
    config_stub.val.colors.webpage.darkmode.enabled = True
    config_stub.val.colors.webpage.darkmode.policy.images = image_policy

    versions = version.WebEngineVersions.from_pyqt(qversion)
    darkmode_settings = darkmode.settings(versions=versions, special_flags=[])

    # Both should produce the same ImagePolicy=2 without classifier policy
    dark_mode_settings = darkmode_settings.get('dark-mode-settings', [])
    image_policies = [setting for setting in dark_mode_settings if setting[0] == 'ImagePolicy']
    classifier_policies = [setting for setting in dark_mode_settings if setting[0] == 'ImageClassifierPolicy']

    assert len(image_policies) == 1, "Should have exactly one ImagePolicy"
    assert image_policies[0][1] == '2', "Should be ImagePolicy=2 (smart)"
    assert len(classifier_policies) == 0, "Should have no ImageClassifierPolicy on older Qt"


def test_chromium_tuple_none_handling():
    """Test that chromium_tuple can return None for unmapped values."""
    # Test with a setting that has a mapping
    setting = darkmode._Setting('test', 'TestKey', {'valid': '1'})

    # Valid value should return tuple
    result = setting.chromium_tuple('valid')
    assert result == ('TestKey', '1')

    # Invalid value should return None
    result = setting.chromium_tuple('invalid')
    assert result is None

    # Test with a setting that has no mapping (should always return tuple)
    setting_no_mapping = darkmode._Setting('test', 'TestKey', None)
    result = setting_no_mapping.chromium_tuple('any_value')
    assert result == ('TestKey', 'any_value')


def test_options(configdata_init):
    """Make sure all darkmode options have the right attributes set."""
    for name, opt in configdata.DATA.items():
        if not name.startswith('colors.webpage.darkmode.'):
            continue

        assert not opt.supports_pattern, name
        assert opt.restart, name

        if opt.backends:
            # On older Qt versions, this is an empty list.
            assert opt.backends == [usertypes.Backend.QtWebEngine], name

        if opt.raw_backends is not None:
            assert not opt.raw_backends['QtWebKit'], name
