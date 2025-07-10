from setuptools import setup, find_packages

setup(
    name="pyaquarite",
    version="0.0.1",
    packages=find_packages(),
    install_requires=[
        "aiohttp",
        "google-cloud-firestore",
        "google-auth"
    ],
    author="Your Name",
    description="Aquarite Python API Client",
    url="https://github.com/yourusername/pyaquarite",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
)
