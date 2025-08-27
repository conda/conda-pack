import os
import tempfile
from unittest.mock import patch

import pytest

from conda_pack.compat import on_win
from conda_pack.prefixes import text_replace, update_prefix


class TestTextReplace:
    """Test the text_replace function for Windows extended-length path handling."""

    def test_basic_text_replacement(self):
        """Test basic placeholder replacement functionality."""
        data = b"#!/usr/bin/env python\nprint('/old/prefix/path')"
        placeholder = "/old/prefix"
        new_prefix = "/new/prefix"

        result = text_replace(data, placeholder, new_prefix)
        expected = b"#!/usr/bin/env python\nprint('/new/prefix/path')"
        assert result == expected

    @pytest.mark.skipif(not on_win, reason="Windows-specific test")
    def test_windows_extended_length_path_cleanup(self):
        """Test that Windows extended-length paths are cleaned up in text replacement."""
        # Test data with various extended-length path patterns
        test_data = b"#!/usr/bin/env python\npath1=\\\\?\\C:\\long\\path\npath2=//?/C:/long/path"
        placeholder = "/old/prefix"
        new_prefix = "/new/prefix"

        result = text_replace(test_data, placeholder, new_prefix)

        # Verify that extended-length prefixes are removed
        assert b'\\\\?\\' not in result
        assert b'//?/' not in result

        # The paths should now be clean
        expected = b"#!/usr/bin/env python\npath1=C:\\long\\path\npath2=C:/long/path"
        assert result == expected

    @pytest.mark.skipif(not on_win, reason="Windows-specific test")
    def test_windows_extended_length_path_with_placeholder_replacement(self):
        """Test extended-length path cleanup combined with placeholder replacement."""
        # Data containing both placeholder and extended-length paths
        test_data = b"#!/usr/bin/env python\nOLD_PREFIX=/old/prefix\npath=\\\\?\\C:\\long\\path"
        placeholder = "/old/prefix"
        new_prefix = "/new/prefix"

        result = text_replace(test_data, placeholder, new_prefix)

        # Both placeholder replacement and extended-length cleanup should occur
        assert b'/old/prefix' not in result
        assert b'/new/prefix' in result
        assert b'\\\\?\\' not in result

        expected = b"#!/usr/bin/env python\nOLD_PREFIX=/new/prefix\npath=C:\\long\\path"
        assert result == expected

    @pytest.mark.skipif(not on_win, reason="Windows-specific test")
    def test_windows_multiple_extended_length_patterns(self):
        """Test cleanup of multiple different extended-length path patterns."""
        test_data = (
            b"path1=\\\\?\\C:\\first\\path\n"
            b"path2=//?/D:/second/path\n"
            b"path3=\\\\?\\E:\\third\\path\n"
            b"path4=//?/F:/fourth/path"
        )
        placeholder = "/dummy"
        new_prefix = "/dummy"

        result = text_replace(test_data, placeholder, new_prefix)

        # All extended-length prefixes should be removed
        assert b'\\\\?\\' not in result
        assert b'//?/' not in result

        expected = (
            b"path1=C:\\first\\path\n"
            b"path2=D:/second/path\n"
            b"path3=E:\\third\\path\n"
            b"path4=F:/fourth/path"
        )
        assert result == expected

    @pytest.mark.skipif(on_win, reason="Non-Windows test")
    def test_non_windows_no_extended_length_cleanup(self):
        """Test that extended-length path patterns are preserved on non-Windows."""
        test_data = b"path1=\\\\?\\C:\\long\\path\npath2=//?/D:/long/path"
        placeholder = "/old/prefix"
        new_prefix = "/new/prefix"

        result = text_replace(test_data, placeholder, new_prefix)

        # On non-Windows, extended-length patterns should be preserved
        assert result == test_data


class TestUpdatePrefix:
    """Test the update_prefix function for Windows extended-length path handling."""

    @pytest.mark.skipif(not on_win, reason="Windows-specific test")
    def test_powershell_extended_length_prefix_removal(self):
        """Test that PowerShell files have extended-length prefixes removed from new_prefix."""
        # Create a temporary PowerShell file
        with tempfile.NamedTemporaryFile(mode='w+b', suffix='.ps1', delete=False) as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(b'$env:PATH = "OLD_PREFIX\\bin"\n')

        try:
            # Test with extended-length prefix that should be removed
            new_prefix_with_extended = "//?/C:/new/prefix"
            placeholder = "OLD_PREFIX"

            with patch('conda_pack.prefixes.replace_prefix') as mock_replace_prefix:
                mock_replace_prefix.return_value = b'$env:PATH = "C:/new/prefix\\bin"\n'

                update_prefix(temp_file_path, new_prefix_with_extended, placeholder, mode='text')

                # Verify replace_prefix was called with the cleaned prefix (no //?/)
                mock_replace_prefix.assert_called_once()
                args = mock_replace_prefix.call_args[0]
                actual_new_prefix = args[3]  # Fourth argument is new_prefix
                assert actual_new_prefix == "C:/new/prefix"
                assert not actual_new_prefix.startswith("//?/")

        finally:
            os.unlink(temp_file_path)

    @pytest.mark.skipif(not on_win, reason="Windows-specific test")
    def test_powershell_normal_prefix_unchanged(self):
        """Test that PowerShell files with normal prefixes are not modified."""
        # Create a temporary PowerShell file
        with tempfile.NamedTemporaryFile(mode='w+b', suffix='.ps1', delete=False) as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(b'$env:PATH = "OLD_PREFIX\\bin"\n')

        try:
            # Test with normal prefix (no extended-length prefix)
            new_prefix_normal = "C:/new/prefix"
            placeholder = "OLD_PREFIX"

            with patch('conda_pack.prefixes.replace_prefix') as mock_replace_prefix:
                mock_replace_prefix.return_value = b'$env:PATH = "C:/new/prefix\\bin"\n'

                update_prefix(temp_file_path, new_prefix_normal, placeholder, mode='text')

                # Verify replace_prefix was called with the unchanged prefix
                mock_replace_prefix.assert_called_once()
                args = mock_replace_prefix.call_args[0]
                actual_new_prefix = args[3]  # Fourth argument is new_prefix
                assert actual_new_prefix == "C:/new/prefix"

        finally:
            os.unlink(temp_file_path)

    @pytest.mark.skipif(not on_win, reason="Windows-specific test")
    def test_non_powershell_extended_length_prefix_preserved(self):
        """Test that non-PowerShell files preserve extended-length prefixes in new_prefix."""
        # Create a temporary Python file
        with tempfile.NamedTemporaryFile(mode='w+b', suffix='.py', delete=False) as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(b'#!/usr/bin/env python\nprint("OLD_PREFIX")\n')

        try:
            # Test with extended-length prefix - should be preserved for non-PS1 files
            new_prefix_with_extended = "//?/C:/new/prefix"
            placeholder = "OLD_PREFIX"

            with patch('conda_pack.prefixes.replace_prefix') as mock_replace_prefix:
                mock_replace_prefix.return_value = (
                    b'#!/usr/bin/env python\n'
                    b'print("//?/C:/new/prefix")\n'
                )

                update_prefix(temp_file_path, new_prefix_with_extended, placeholder, mode='text')

                # Verify replace_prefix called with forward slashes but extended prefix preserved
                mock_replace_prefix.assert_called_once()
                args = mock_replace_prefix.call_args[0]
                actual_new_prefix = args[3]  # Fourth argument is new_prefix
                # Should have forward slashes but keep the //?/ prefix for non-PS1 files
                assert actual_new_prefix == "//?/C:/new/prefix"

        finally:
            os.unlink(temp_file_path)

    @pytest.mark.skipif(not on_win, reason="Windows-specific test")
    def test_windows_backslash_to_forward_slash_conversion(self):
        """Test that Windows paths are converted to forward slashes in text mode."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w+b', suffix='.txt', delete=False) as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(b'PATH=OLD_PREFIX\\bin\n')

        try:
            # Test with backslashes that should be converted to forward slashes
            new_prefix_with_backslashes = "C:\\new\\prefix"
            placeholder = "OLD_PREFIX"

            with patch('conda_pack.prefixes.replace_prefix') as mock_replace_prefix:
                mock_replace_prefix.return_value = b'PATH=C:/new/prefix\\bin\n'

                update_prefix(temp_file_path, new_prefix_with_backslashes, placeholder, mode='text')

                # Verify replace_prefix was called with forward slashes
                mock_replace_prefix.assert_called_once()
                args = mock_replace_prefix.call_args[0]
                actual_new_prefix = args[3]  # Fourth argument is new_prefix
                assert actual_new_prefix == "C:/new/prefix"
                assert "\\" not in actual_new_prefix

        finally:
            os.unlink(temp_file_path)

    @pytest.mark.skipif(on_win, reason="Non-Windows test")
    def test_non_windows_no_path_modifications(self):
        """Test that non-Windows systems don't modify paths."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w+b', suffix='.py', delete=False) as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(b'#!/usr/bin/env python\nprint("OLD_PREFIX")\n')

        try:
            # Test with backslashes and extended-length prefix - should be preserved on non-Windows
            new_prefix_windows_style = "\\\\?\\C:\\new\\prefix"
            placeholder = "OLD_PREFIX"

            with patch('conda_pack.prefixes.replace_prefix') as mock_replace_prefix:
                mock_replace_prefix.return_value = (
                    b'#!/usr/bin/env python\nprint("\\\\?\\C:\\new\\prefix")\n'
                )

                update_prefix(temp_file_path, new_prefix_windows_style, placeholder, mode='text')

                # Verify replace_prefix was called with unchanged prefix
                mock_replace_prefix.assert_called_once()
                args = mock_replace_prefix.call_args[0]
                actual_new_prefix = args[3]  # Fourth argument is new_prefix
                assert actual_new_prefix == "\\\\?\\C:\\new\\prefix"

        finally:
            os.unlink(temp_file_path)

    def test_binary_mode_no_path_modifications(self):
        """Test that binary mode doesn't trigger Windows path modifications."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w+b', suffix='.exe', delete=False) as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(b'\x00OLD_PREFIX\x00\x00\x00')

        try:
            # Test with extended-length prefix in binary mode - should not be modified
            new_prefix_with_extended = "//?/C:/new/prefix" if on_win else "//?/C:/new/prefix"
            placeholder = "OLD_PREFIX"

            with patch('conda_pack.prefixes.replace_prefix') as mock_replace_prefix:
                mock_replace_prefix.return_value = b'\x00//?/C:/new/prefix\x00'

                update_prefix(temp_file_path, new_prefix_with_extended, placeholder, mode='binary')

                # Verify replace_prefix was called with unchanged prefix (no path modifications in
                # binary mode)
                mock_replace_prefix.assert_called_once()
                args = mock_replace_prefix.call_args[0]
                actual_new_prefix = args[3]  # Fourth argument is new_prefix
                assert actual_new_prefix == "//?/C:/new/prefix"

        finally:
            os.unlink(temp_file_path)
