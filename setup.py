from pathlib import Path

from setuptools import find_packages, setup


def read_package_metadata(
    package_path: str | Path = None,
) -> dict[str, str]:
    def parse_line(line: str) -> tuple[str, str] | None:
        assignment = line.split("=", 1)
        if len(assignment) == 2:
            var, value = assignment
            var = var.strip().strip("_")
            value = value.strip().strip("'\"")
            return var, value

    if package_path is None:
        package_path = Path(__file__).parent
        package_path = package_path / package_path.name

    with open(package_path / "__init__.py") as f:
        content = f.read()

    fields = dict()
    for line in content.splitlines():
        res = parse_line(line)
        if res:
            fields[res[0]] = res[1]

    return fields


package_metadata = read_package_metadata()
print(package_metadata)

setup(
    name="piconetcontrol",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.9",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Hardware",
        "Topic :: System :: Networking",
    ],
    # python_requires=">=3.11",
    long_description=Path("README.rst").read_text(),
    long_description_content_type="text/x-rst",
    **package_metadata,
)
