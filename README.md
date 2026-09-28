# Dragon Claw for Home Assistant

Control PCs running the [Dragon Claw agent](https://github.com/Janrupf/dragon-claw) from Home Assistant.

- **Auto-discovery** over mDNS (`_dragon-claw._tcp`). If the PC gets a new IP, the entry follows it.
- **Power switch**: on = Wake-on-LAN, off = shut down, state = whether the agent is reachable (polled every 30s).
- **Buttons** for every agent action (reboot, reboot to firmware, lock, log out, suspend, hibernate, hybrid suspend) plus **Wake**. Buttons for actions the PC doesn't support stay unavailable.

## Install (HACS)

1. HACS → ⋮ → *Custom repositories* → add this repo's URL, type *Integration*.
2. Install **Dragon Claw**, restart Home Assistant.
3. Discovered PCs show up under *Settings → Devices & services*. You can also add one by hand (default port `37121`).

## Wake-on-LAN

Enter the PC's MAC address when you add it. If Home Assistant has seen the PC recently, the MAC is filled in from the ARP table. To change it later, use *Reconfigure* on the entry.
WoL has to be turned on in the PC's BIOS/UEFI and on its network adapter. The magic packet goes to `255.255.255.255:9`, so Home Assistant needs to be on the same L2 network as the PC.

> The agent has no authentication. Anyone on your LAN can already do what this integration does.

Icon from [Janrupf/dragon-claw](https://github.com/Janrupf/dragon-claw), MIT License, © 2023 Janrupf.
