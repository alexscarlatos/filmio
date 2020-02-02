import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="filmio",
    version="0.0.1",
    author="Alex Scarlatos",
    author_email="ajscarlatos@gmail.com",
    description="A utility for syncing video to source audio, perhaps for your films",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/alexscarlatos/filmio",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent", # TODO: how to have builds for multiple OS?
    ],
    python_requires='>=3.6', # TODO: test with 3.6
    install_requires=[
        'wavio',
        'scipy',
        'numpy',
    ],
    dependency_links=[
        'http://www.fon.hum.uva.nl/praat/praat6109_mac64.dmg', # TODO: how does this work? and how to make windows work too?
    ],
    entry_points = {
        'console_scripts': ['filmio=filmio.__main__:main'],
    },
)
