"""File I/O utilities for reading, writing, and managing files.

Provides comprehensive file operations including:
- File/directory existence checks and scanning
- Text, JSON, and pickle file operations
- Spreadsheet I/O (Excel, ODF, CSV, Numbers)
- File permissions management
- DataFrame utilities

:module:    file_io.py
:class:     FileMethods
:author:    GM (genuinemerit @ pm.me)
"""

from __future__ import annotations

import json
import pandas as pd
import pickle
import shutil

from numbers_parser import Document as NumbersDoc
from os import remove, symlink, makedirs
from pathlib import Path

from shared.utils.shell import ShellMethods

shell_methods = ShellMethods()


class FileMethods(object):
    """File IO utilities."""

    def __init__(self):
        """Initialize FileMethods object."""
        pass

    # Read methods
    # ==============================================================

    @classmethod
    def is_file_or_dir(cls, path: str) -> bool:
        """
        Check if file or directory exists.

        :param path: Legit path to file or dir location.
        :return: True if exists, False otherwise.
        """
        return Path(path).exists()

    @classmethod
    def scan_dir(cls, dir_path: str, file_pattern: str = "") -> list:
        """
        Scan a directory for files matching a specific pattern.
        This method returns PosixPath objects, not strings.

        :param dir_path: Path to the directory.
        :param file_pattern: Pattern to match the file names. Allow * as wildcard.
        :return: List of file paths (PosixPath structures) matching the pattern.
        """
        srch = file_pattern.split("*")
        try:
            dir_path = Path(dir_path)
            if dir_path.exists() and dir_path.is_dir():
                files = [
                    f for f in dir_path.iterdir() if all(s in f.name for s in srch)
                ]
                return sorted(files)
        except Exception as err:
            raise err
        return []

    @classmethod
    def get_dir(cls, path: str):
        """
        Read a directory and return its contents.

        :param path: Legit path to directory location.
        :return: List of directory contents or None if not found.
        """
        try:
            path_obj = Path(path)
            if path_obj.exists() and path_obj.is_dir():
                return [str(f) for f in path_obj.iterdir()]
        except Exception as err:
            raise err
        return None

    @classmethod
    def get_absolute_path(cls, path: str) -> str:
        """
        Convert provided path to an absolute path.

        :param path: Legit path to file or dir location.
        :return: Absolute path as string.
        """
        return str(Path(path).resolve())

    @classmethod
    def get_file(cls, path: str) -> str:
        """
        Read in an entire file and return its contents.

        :param path: Legit path to file location.
        :return: File content as text.
        """
        try:
            abs_path = Path(path).resolve()
            with open(abs_path, "r") as f:
                return f.read().strip()
        except Exception as err:
            print(shell_methods.show_trace(err))
        return ""

    @classmethod
    def get_numbers_data(cls, file_path: str, sheet_index: int = 0) -> pd.DataFrame:
        """
        Read data from Numbers (MacOS) spreadsheet tab and return as a DataFrame.

        :param file_path: Path to the workbook.
        :param sheet_index: Index of sheet to load.
        :return: DataFrame of the sheet.
        """
        doc = NumbersDoc(file_path)
        sheets = doc.sheets
        tables = sheets[sheet_index].tables
        data = tables[0].rows(values_only=True)
        return pd.DataFrame(data[1:], columns=data[0])

    def get_spreadsheet_data(self, file_path: str, sheet: str = "") -> pd.DataFrame:
        """
        Get data from Excel, ODF, CSV (tab), or MacOS Numbers spreadsheet.

        :param file_path: Path to the workbook.
        :param sheet: Name or index of sheet to load. Optional.
        :return: DataFrame of the sheet.
        """
        ss_type = file_path.split(".")[-1].lower()
        sheet_nm = None if not sheet else sheet
        if ss_type in ("xlsx", "xls"):
            return pd.read_excel(file_path, sheet_name=sheet_nm)
        elif ss_type == "ods":
            return pd.read_excel(file_path, engine="odf", sheet_name=sheet_nm)
        elif ss_type == "csv":
            return pd.read_csv(file_path)
        elif ss_type == "numbers":
            return self.get_numbers_data(file_path, int(sheet_nm))
        else:
            raise ValueError(f"Unsupported file type: {file_path}")

    @classmethod
    def get_json_file(cls, path: str):
        """
        Read in an entire JSON file and return its contents as dict.

        :param path: Legit path to JSON file location.
        :return: File content as dictionary or empty dict on error.
        """
        try:
            abs_path = Path(path).resolve()
            return json.loads(cls.get_file(abs_path))
        except Exception as e:
            print(shell_methods.show_trace(e))
        return {}

    @classmethod
    def unpickle_object(cls, path: str):
        """
        Unpickle an object.

        :param path: Legit path to pickled object location.
        :return: Unpickled object.
        """
        try:
            abs_path = Path(path).resolve()
            with open(abs_path, "rb") as f:
                return pickle.load(f)
        except Exception as err:
            raise err

    # Write methods
    # ==============================================================
    @classmethod
    def make_dir(cls, path: str):
        """
        Create directory at specified location.

        :param path: Legit path to create dir.
        """
        try:
            makedirs(path, exist_ok=True)
        except Exception as err:
            raise err

    @classmethod
    def delete_file(cls, path: str):
        """
        Remove a file.

        :param path: Valid path to file to be removed.
        """
        try:
            remove(path)
        except OSError as err:
            raise err

    @classmethod
    def copy_one_file(cls, path_from: str, path_to: str):
        """
        Copy one file from source to target.

        :param path_from: Full path of file to be moved.
        :param path_to: Destination path.
        """
        try:
            shutil.copy2(path_from, path_to)
        except OSError as err:
            raise err

    @classmethod
    def copy_all_files(cls, path_from: str, path_to: str):
        """
        Copy all files in dir from source to target.

        :param path_from: Full path of a dir with files to be moved.
        :param path_to: Destination path.
        """
        try:
            cmd = f"cp -rf {path_from}/* {path_to}"
            ok, msg = shell_methods.run_cmd(cmd)
            if not ok:
                raise Exception(msg)
        except Exception as err:
            raise err

    @classmethod
    def make_link(cls, link_from: str, link_to: str):
        """
        Make a symbolic link from the designated file.

        :param link_from: Path of file to be linked from.
        :param link_to: Destination path of the link.
        """
        try:
            symlink(link_from, link_to)
        except OSError as err:
            raise err

    @classmethod
    def append_file(cls, path: str, text: str):
        """
        Append text to specified text file.

        :param path: Legit path to a text file location.
        :param text: Text to append to the file.
        """
        try:
            with open(path, "a+") as f:
                f.write(text)
        except Exception as err:
            raise err

    @classmethod
    def write_file(cls, path: str, data, file_type: str = "w+") -> bool:
        """
        Write or overwrite data to specified file.

        :param path: Legit path to a file location.
        :param data: Data to write to the file.
        :param file_type: Mode to open the file, default is "w+".
        :return: True if successful, False otherwise.
        """
        try:
            with open(path, file_type) as f:
                f.write(data)
        except Exception as e:
            raise f"Error writing file: {shell_methods.show_trace(e)}"
            return False
        return True

    @classmethod
    def write_df_to_csv(cls, df: pd.DataFrame, csv_path: str):
        """
        Save dataframe as CSV.

        :param df: Dataframe to save as CSV.
        :param csv_path: Path to the CSV file to create.
        """
        df.to_csv(csv_path, index=False)

    @classmethod
    def pickle_object(cls, path: str, obj):
        """
        Pickle an object.

        :param path: Legit path to target object/file location.
        :param obj: Object to be pickled (source).
        """
        try:
            with open(path, "wb") as obj_file:
                pickle.dump(obj, obj_file)
        except Exception as err:
            raise err

    @classmethod
    def rename_file(cls, path: str, new_name: str):
        """
        Rename a file.

        :param path: Path to the file to be renamed.
        :param new_name: New name for the file.
        """
        try:
            abs_path = Path(path).resolve()
            ext = abs_path.suffix
            new_path = abs_path.parent / f"{new_name}{ext}"
            abs_path.rename(new_path)
        except Exception as err:
            raise err

    # CHMOD methods
    # ==============================================================
    @classmethod
    def make_readable(cls, path: str):
        """
        Make file at path readable for all.

        :param path: File to make readable.
        """
        cls._change_permissions(path, "u=rw,g=r,o=r")

    @classmethod
    def make_writable(cls, path: str):
        """
        Make file at path writable for all.

        :param path: File to make writable.
        """
        cls._change_permissions(path, "u=rwx,g=rwx,o=rwx")

    @classmethod
    def make_executable(cls, path: str):
        """
        Make file at path executable for all.

        :param path: File to make executable.
        """
        cls._change_permissions(path, "u=rwx,g=rx,o=rx")

    @classmethod
    def _change_permissions(cls, path: str, mode: str):
        """
        Change file permissions using chmod.

        :param path: Path to the file whose permissions are to be changed.
        :param mode: Permission mode string.
        """
        try:
            cmd = f"chmod {mode} {path}"
            ok, msg = shell_methods.run_cmd(cmd)
            if not ok:
                raise Exception(msg)
        except Exception as err:
            raise err

    # Shaping and analysis methods
    # ==============================================================

    @classmethod
    def get_df_col_names(cls, df: pd.DataFrame) -> list:
        """
        Get list of column names from a dataframe.

        :param df: Dataframe to extract column names from.
        :return: List of column names.
        """
        return list(df.columns.values)

    @classmethod
    def get_df_col_unique_vals(cls, col: str, df: pd.DataFrame) -> list:
        """
        For a dataframe column, return list of unique values.

        :param col: Column name to find unique values in.
        :param df: Dataframe containing the column.
        :return: Sorted list of unique values in the column.
        """
        u_vals = df.dropna(subset=[col]).drop_duplicates(subset=[col])
        vals = u_vals[col].values.tolist()
        return sorted(vals)

    @classmethod
    def get_df_metadata(cls, df: pd.DataFrame) -> dict:
        """
        Get metadata from a dataframe.

        :param df: Dataframe to extract metadata from.
        :return: Dictionary with row count and unique values per column.
        """
        df_meta = {"row_count": len(df.index), "columns": {}}
        cols = cls.get_df_col_names(df)
        for col_nm in cols:
            df_meta["columns"][col_nm] = cls.get_df_col_unique_vals(col_nm, df)
        return df_meta

    @classmethod
    def diff_files(cls, file_a: str, file_b: str) -> str:
        """
        Diff two files and return the result.

        :param file_a: Path to the first file.
        :param file_b: Path to the second file.
        :return: Result of the diff command as a string.
        """
        try:
            cmd = f"diff {file_a} {file_b}"
            ok, msg = shell_methods.run_cmd(cmd)
            if not ok:
                raise Exception(msg)
            return msg
        except Exception as err:
            raise err
