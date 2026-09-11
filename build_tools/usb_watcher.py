import time
import os
import subprocess
import string
import ctypes

# =============================================================
#  CONFIGURA ESTOS DOS VALORES
# =============================================================

# Etiqueta (nombre) que le pondrás al pendrive. Para ponérsela:
#   clic derecho en la unidad en el Explorador > Cambiar nombre
#   o en cmd (como administrador): label X: CORTANA_USB
VOLUME_LABEL = "CORTANA_USB"

# Ruta del ejecutable DENTRO del pendrive, relativa a la raíz de la unidad.
EXE_RELATIVE_PATH = r"CORTANA 3.0\dist\Cortana.exe"

POLL_SECONDS = 3


def get_volume_label(drive_letter):
    kernel32 = ctypes.windll.kernel32
    volume_name_buffer = ctypes.create_unicode_buffer(1024)
    fs_name_buffer = ctypes.create_unicode_buffer(1024)
    try:
        kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(drive_letter + "\\"),
            volume_name_buffer,
            ctypes.sizeof(volume_name_buffer),
            None,
            None,
            None,
            fs_name_buffer,
            ctypes.sizeof(fs_name_buffer),
        )
        return volume_name_buffer.value
    except Exception:
        return ""


def find_pendrive():
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for i, letter in enumerate(string.ascii_uppercase):
        if bitmask & (1 << i):
            drive = f"{letter}:"
            label = get_volume_label(drive)
            if label.strip().upper() == VOLUME_LABEL.upper():
                return drive
    return None


def main():
    already_launched = False

    print("CORTANA WATCHER activo.")
    print(f"Esperando el pendrive con etiqueta '{VOLUME_LABEL}'...")

    while True:
        try:
            drive = find_pendrive()

            if drive and not already_launched:
                exe_path = os.path.join(drive + "\\", EXE_RELATIVE_PATH)

                if os.path.isfile(exe_path):
                    print(f"Pendrive detectado en {drive}. Iniciando Cortana...")
                    try:
                        subprocess.Popen(
                            [exe_path],
                            cwd=os.path.dirname(exe_path),
                        )
                        already_launched = True
                    except Exception as error:
                        print("No pude iniciar Cortana:", error)
                else:
                    print(f"Pendrive detectado pero no encontré: {exe_path}")

            elif not drive:
                already_launched = False

        except Exception as error:
            print("ERROR EN EL WATCHER:", error)

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()