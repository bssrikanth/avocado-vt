#
# library for cpu related helper functions
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; specifically version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# See LICENSE for more details.
#
# Copyright: Red Hat (c) 2023 and Avocado contributors
# Author: Houqi Zuo <hzuo@redhat.com>
import re

from avocado.utils import process


def get_cpu_info():
    """
    Return information about the CPU information.

    :return: cpu information
    :rtype: list[dict]
    """
    cpu_info = list()
    with open("/proc/cpuinfo") as fd:
        processors = fd.read().strip().split("\n\n")
    for processor in processors:
        if processor != "":
            info = dict(
                map(
                    lambda x: [i.strip() for i in x.split(":", 1)],
                    processor.split("\n"),
                )
            )
            cpu_info.append(info)

    return cpu_info


def get_cpu_model_name():
    """
    Return physical cpu model.

    :return: cpu model name
    :rtype: string
    :raises: An OSError will be raised if it's NOT available on the platform
    """
    cpu_model = process.run("lscpu").stdout_text
    cpu_model_re = "(?m)^[mM]odel name:.*$"
    cpu_model = re.search(cpu_model_re, cpu_model)
    if not cpu_model:
        raise OSError("The cpu model name was NOT found!")
    cpu_model = cpu_model.group()
    return cpu_model.split(":", 1)[-1].strip()


def get_cpu_flags():
    """
    Return a list of the CPU flags.

    :return: cpu flags
    :rtype: list[string]
    :raises: An OSError will be raised if it's NOT available on the platform
    """
    cpu_flags_re = "(?m)^flags\s+:\s+([\w\s]+)$"
    with open("/proc/cpuinfo") as fd:
        cpu_info = fd.read()
    cpu_flags = re.search(cpu_flags_re, cpu_info)
    if not cpu_flags:
        raise OSError("The cpu flags were NOT found!")
    cpu_flags = cpu_flags.groups()[0]
    return re.split("\s+", cpu_flags.strip())


def get_cpu_features():
    """
    Return a list of the CPU features.

    :return: cpu features
    :rtype: list[string]
    :raises: An OSError will be raised if it's NOT available on the platform
    """
    cpu_features_re = "(?m)^[fF]eatures\s+:\s+([\w\s]+)$"
    with open("/proc/cpuinfo") as fd:
        cpu_info = fd.read()
    cpu_features = re.search(cpu_features_re, cpu_info)
    if not cpu_features:
        raise OSError("The cpu features were NOT found!")
    cpu_features = cpu_features.groups()[0]
    return re.split("\s+", cpu_features.strip())


def get_cpu_vendor_id():
    """
    Return the name of the CPU vendor ID.

    :return: the name of the CPU vendor ID in string
    :rtype: string
    :raises: An OSError will be raised if it's NOT available on the platform
    """
    vendor_re = "(?m)^vendor_id\s+:\s+(\w+)$"
    with open("/proc/cpuinfo") as fd:
        cpu_info = fd.read()
    vendor_id = re.search(vendor_re, cpu_info)
    if not vendor_id:
        raise OSError("The vendor id was NOT found!")
    vendor_id = vendor_id.groups()[0]
    return vendor_id


def get_cpu_family():
    """
    Return the name of cpu family.

    :return: the name of the cpu family in string
    :rtype: string
    :raises: An OSError will be raised if it's NOT available on the platform
    """
    cpu_family_re = "cpu family\s+:\s+(\w+)"
    with open("/proc/cpuinfo") as fd:
        cpu_info = fd.read()
    cpu_family = re.search(cpu_family_re, cpu_info)
    if not cpu_family:
        raise OSError("The cpu family was NOT found!")
    cpu_family = cpu_family.groups()[0]
    return cpu_family


def get_amd_platform(min_platform=None):
    """
    Return the AMD platform codename for the host CPU and optionally
    verify it meets a minimum platform requirement.

    Maps CPU family and model to a platform name based on the ranges
    defined in arch/x86/kernel/cpu/amd.c in the upstream Linux kernel.

    Supported platforms in generation order:
      - milan:   family=25, model 0-15
      - genoa:   family=25, model 16-31
      - bergamo: family=25, model 160-175
      - turin:   family=26, model 0-47
      - venice:  family=26, model 80-95, 128-175, 192-239

    :param min_platform: optional minimum platform required by the caller
        (e.g. "milan"). If the detected platform is older than this,
        an OSError is raised. Case-insensitive. None means no check.
    :type min_platform: str or None
    :return: detected platform codename (e.g. "milan", "genoa", "venice")
    :rtype: str
    :raises ValueError: if min_platform is not a recognised platform name.
    :raises OSError: if the CPU vendor is not AMD, the family/model is
        unrecognised, or the host platform is older than min_platform.
    """
    # Ordered from oldest to newest. Each entry:
    # (platform_name, family, [(model_min, model_max), ...])
    # Ranges sourced from arch/x86/kernel/cpu/amd.c (upstream Linux kernel).
    amd_platforms = [
        ("milan",   25, [(0,   15)]),
        ("genoa",   25, [(16,  31)]),
        ("bergamo", 25, [(160, 175)]),
        ("turin",   26, [(0,   47)]),
        ("venice",  26, [(80,  95), (128, 175), (192, 239)]),
    ]
    platform_order = [p[0] for p in amd_platforms]

    if min_platform is not None:
        min_platform = min_platform.lower()
        if min_platform not in platform_order:
            raise ValueError(
                f"Unknown platform '{min_platform}'. "
                f"Valid options: {', '.join(platform_order)}"
            )

    if get_cpu_vendor_id() != "AuthenticAMD":
        raise OSError("Platform detection is only supported on AMD CPUs.")

    family = int(get_cpu_family())
    model_re = "(?m)^model\s+:\s+(\d+)$"
    with open("/proc/cpuinfo") as fd:
        cpu_info = fd.read()
    model_match = re.search(model_re, cpu_info)
    if not model_match:
        raise OSError("The cpu model was NOT found!")
    model = int(model_match.groups()[0])

    detected = None
    for platform, fam, ranges in amd_platforms:
        if fam == family and any(lo <= model <= hi for lo, hi in ranges):
            detected = platform
            break

    if detected is None:
        raise OSError(
            f"Unrecognised AMD platform: family={family}, model={model}."
        )

    if min_platform is not None:
        detected_idx = platform_order.index(detected)
        required_idx = platform_order.index(min_platform)
        if detected_idx < required_idx:
            raise OSError(
                f"Detected platform '{detected}' is older than the "
                f"required minimum '{min_platform}'."
            )

    return detected


def get_cpu_stepping():
    """
    Return the name of cpu stepping.

    :return: the name of the cpu stepping in string
    :rtype: string
    :raises: An OSError will be raised if it's NOT available on the platform
    """
    stepping_re = "(?m)^stepping\s+:\s+(\w+)$"
    with open("/proc/cpuinfo") as fd:
        cpu_info = fd.read()
    stepping = re.search(stepping_re, cpu_info)
    if not stepping:
        raise OSError("The cpu stepping was NOT found!")
    stepping = stepping.groups()[0]
    return stepping
