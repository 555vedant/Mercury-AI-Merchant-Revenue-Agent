"""Mercury — AI Merchant Revenue Agent"""

from setuptools import setup, find_packages

import os


def read_readme():
    with open("README.md", "r", encoding="utf-8") as f:
        return f.read()


def read_requirements():
    requirements_path = os.path.join(
        os.path.dirname(__file__),
        "requirements.txt"
    )

    if os.path.exists(requirements_path):
        with open(requirements_path, "r", encoding="utf-8") as f:
            return [
                line.strip()
                for line in f
                if line.strip() and not line.startswith("#")
            ]

    return []


setup(
    name="mercury",
    version="0.1.0",
    description="AI Merchant Revenue Agent for agentic commerce",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords="AI merchant agentic commerce revenue negotiation",
)