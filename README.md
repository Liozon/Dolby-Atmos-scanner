# Dolby Atmos scanner

This Python script scans your folders and looks for Dolby Atmos audio tracks in metadata.

- [Dolby Atmos scanner](#dolby-atmos-scanner)
  - [Functionalities](#functionalities)
  - [Screens of the interface](#screens-of-the-interface)
    - [General interface](#general-interface)
    - [Completed scan](#completed-scan)
    - [Scan with language filter](#scan-with-language-filter)
  - [Why this script ?](#why-this-script-)

## Functionalities

This script supports the following functionalities:

- One or multiple folders scan
- Export the results to a TXT or CSV file
- Audio language filter
- Cached results, to avoid scanning again a previous scanned file

## Screens of the interface

### General interface

![Dolby Atmos scanner completed scan](https://raw.githubusercontent.com/Liozon/Dolby-Atmos-scanner/refs/heads/main/images/Dolby%20Atmos%20scanner.png)

### Completed scan

![Dolby Atmos scanner completed scan](https://raw.githubusercontent.com/Liozon/Dolby-Atmos-scanner/refs/heads/main/images/Scan%20completed.png)

### Scan with language filter

![Dolby Atmos scanner completed scan](https://raw.githubusercontent.com/Liozon/Dolby-Atmos-scanner/refs/heads/main/images/Scan%20with%20lang%20filter.png)

## Why this script ?

Like many people, I have a local media server with various audio formats. Since I have now a Dolby Atmos home theatre system, I wanted to find all the audio track supporting Dolby Atmos. For example, Plex doesn't allow you to filter content based on audio type, so I had to come up with this script to scan the files and identify which files has a Dolby Atmos audio track.