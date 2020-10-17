import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="filmio",
    version="0.0.1",
    author="Alexander Scarlatos",
    author_email="ajscarlatos@gmail.com",
    description="Find the best audio tracks to match your videos, perhaps for your films.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/alexscarlatos/filmio",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
    install_requires=[
        'wavio',
        'scipy',
        'numpy',
        'pylint',
        'praat-parselmouth'
    ],
    entry_points = {
        'console_scripts': ['filmio=filmio.__main__:main'],
    },
)
