import os
import sys
import subprocess

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Required argument: <path to xorg.conf>")
        sys.exit(1)

    xorg_config = sys.argv[1]

    lspci_p = subprocess.Popen(['lspci'], stdout=subprocess.PIPE)
    lspci_vga_p = subprocess.Popen(['grep', 'VGA'], stdin=lspci_p.stdout, stdout=subprocess.PIPE)
    lspci_p.stdout.close()

    vga_devices = lspci_vga_p.communicate()[0]

    gpus = []

    for line in vga_devices.split('\n'):
        if len(line) == 0:
            continue
        if "Cirrus" in line:
            continue
        if "NVIDIA Corporation" in line:
            bus_id_hex = line.split(' ')[0]
            bus_id0, bus_id12 = bus_id_hex.split(':')[0], bus_id_hex.split(':')[1]
            bus_id1, bus_id2 = bus_id12.split('.')
            bus_id_decimal = "{}:{}:{}".format(int(bus_id0, 16), int(bus_id1, 16), int(bus_id2, 16))
            gpus.append((line, bus_id_hex, bus_id_decimal))

    if len(gpus) == 0:
        print("No GPUs detected with 'lspci | grep VGA'!")
        sys.exit(1)

    print("{} GPUs detected:".format(len(gpus)))
    print("  {: <10s} {: <10s} {}".format("BusID hex", "BusID dec", "lspci output"))
    for line, bus_id_hex, bus_id_decimal in gpus:
        print("  {: <10s} {: <10s} {}".format(bus_id_hex, bus_id_decimal, line))

    print("Fixing xorg.conf {}...".format(xorg_config))
    xorg_config_backup = xorg_config + ".backup"
    xorg_config_new = xorg_config + ".fixed.tmp"

    with open(xorg_config, 'r') as config:
        lines = config.readlines()

    # 1. Delete whole section ServerLayout (comment it with # symbol)
    # 2. Delete whole section Screen (comment it with # symbol)
    # 3. Add line with BusID in section Device (taken from output of lspci | grep VGA)
    section_start = "Section \""
    section_end   = "EndSection\n"
    sections_to_delete = ["ServerLayout", "Screen"]

    sections_deleted = []
    device_section_found = False

    print("  Writing fixed xorg.conf to {}".format(xorg_config_new))
    with open(xorg_config_new, 'w') as updated:
        current_section = None
        for line in lines:
            removed = False

            if current_section is None and section_start in line:
                current_section = line[len(section_start):-2]
                if current_section in sections_to_delete:
                    print("  Section {} deleted!".format(current_section))
                    sections_deleted.append(current_section)

            if current_section in sections_to_delete:
                removed = True

            if current_section is not None and line == section_end:
                if current_section == "Device":
                    _, _, bus_id_decimal = gpus[0]
                    print("  BusID {} added!".format(bus_id_decimal))
                    updated.write("    BusID          \"PCI:{}\"\n".format(bus_id_decimal))
                    device_section_found = True
                current_section = None

            if removed:
                updated.write("#{}".format(line))
            else:
                updated.write("{}".format(line))

    if not device_section_found:
        print("Section \"Device\" was not found!")
        sys.exit(1)
    for section in sections_to_delete:
        if section not in sections_deleted:
            print("Section \"{}\" was not found!".format(section))
            sys.exit(1)

    os.rename(xorg_config, xorg_config_backup)
    print("  Backup saved to {}".format(xorg_config_backup))

    os.rename(xorg_config_new, xorg_config)
