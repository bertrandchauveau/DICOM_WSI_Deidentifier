# DICOM_WSI_Deidentifier

To deidentify DICOM whole slide images in conformance to the DICOM basic application level confidentiality profile

This work has been accepted in the Archives of Pathology and Laboratory Medicine. The link to the journal article will be displayed when published.

## 🚀 About
Pathology Departments in their digitization transition are encouraged to adopt the Digital Imaging and Communications in Medicine (DICOM) format for routine diagnosis, leading to a major increase of histopathological image-based research projects using this format. Still, DICOM for whole slide images (WSI) remains an emerging file format, with limited tools currently available for deidentification without coding skills. This project aimed to build an easy-to-use and no-code tool to deidentify DICOM WSI, with feedback on the deidentification process.

This is a Python-based solution to deidentify DICOM WSI in conformance to the DICOM basic application level confidentiality profile (for more information, see https://dicom.nema.org/medical/dicom/current/output/chtml/part15/chapter_e.html).

The solution is available as Windows and MacOS executables created using Flet 1.1.1. The source code is available in this github repository.

The main dependencies are listed in the pyproject.toml

The deidentification process creates from scratch the deidentified WSI (no modification of original files) and includes several steps: (i) the removal of the macro/overview image, which includes the label for some scanners, (ii) the removal of the original label, replaced by a QR code image of the deidentified sample ID, (iii) the removal or modifications of the DICOM metadata in all files, and (iv) the addition of three DICOM tags qualifying the deidentification of each file: “patient identity removed”, “deidentification method” and “longitudinal temporal information modified”.

**WARNING**: The application does not access slide pixel data. As such, **users must ensure that no sensitive information appears on the slide** (e.g. handwritten text). Additionally, free-text fields embedded in some DICOM tags (e.g., OpticalPathDescription, annotation text) are copied as they are and could in theory contain identifying information. You can check for this in the .txt files.

The solution has been tested in these situations:
- Single plane brightfield images, DICOM WSI originating from:
  
    => Leica (Aperio GT450 DX)
  
    => 3DHistech (Pannoramic scan P150, P1000)
  
    => Roche (DP600 and DP200)
  
    => Hamamatsu (S360)
  
    => Olympus/Evident (VS200 and DX VS M1)
  
- Single plex immunofluorescence and multiplane brightfield images:

    => 3DHistech (Pannoramic scan P150)

- Multiplex immunofluorescence images:

    => Olympus/Evident (VS200)

## ⚠️ Important Notice
This application is provided for **RESEARCH AND EDUCATIONAL purposes only**.
By using this application, you agree that your use of this software is at your own risk.

## Usage instructions
The arguments, to be defined through the user interface are:
- path_to_WSI: the path to the folder containing the sensitive DICOM WSI (as folders or zip)
- path_output: the path where the deidentified WSI will be saved
- path to CSV file: an optional CSV file (separator ";") matching original sample reference (or WSI name) with the desired deidentified reference and WSI name. The header of the columns should be: "Original WSI name", "Original ID" and "Deidentified ID". See also the provided template.
- secret key: a string secret key to ensure reproducibility in terms of (i) acquisition date shift (+/- 6 months), (ii) modifications of the DICOM Unique Identifiers (UID) and (iii) modification of the sample identifier and file name.
- identifier of reference: whether the deidentified WSI name and sample reference should be based on the original sample identifier or WSI name
- annotations: whether annotations files should be maintained during the process. Default to False. Beware that maintaining the annotation files is against the DICOM basic application level confidentiality profile. **You should be sure that the graphic element and associated text of the annotation do not contain sensitive information.**
- longitudinal temporal information: whether the date shift should be applied to the original acquisition date/time, as such maintaining the longitudinal temporal information between slides. Default to False, with the use of the date of the deidentification run. If True, in conformance to the Retain Longitudinal Temporal Information Option (see https://dicom.nema.org/medical/dicom/current/output/chtml/part15/sect_E.3.6.html)
- txt file: whether txt files should be created for each deidentified .dcm file, listing DICOM metadata, to verify the integrity of the process

## 📥 Installation
### System Requirements
- Windows: Windows 10 or later (64-bit)
- macOS: macOS Catalina (10.15) or later

### Downloading the Application
- Go to the [Releases page](https://github.com/bertrandchauveau/DICOM_WSI_Deidentifier/releases/latest)
- Download the latest release for your operating system:
  - DICOM_WSI_Deidentifier-windows.zip (for Windows users)
  - DICOM_WSI_Deidentifier-macos.zip (for macOS users)
- Extract the ZIP file to a location of your choice

### 🛡️ Important Security Note
These applications are unsigned. This means that:

- Windows: You'll see a "Windows protected your PC" warning
- macOS: You'll encounter "Gatekeeper" warnings (see below)

This is normal and expected. Download only from [the release page](https://github.com/bertrandchauveau/DICOM_WSI_Deidentifier/releases) of this repository. 
Optionally verify the file against the SHA-256 checksum on the release page.

### For Institutional/Enterprise Devices
If you're installing this on an institutional or corporate device:

- Please check with your IT department first
- Your organization may have strict security policies regarding unsigned applications
- Some institutions require approval for any software installation
- Your IT team can help ensure compliance with local security requirements

### 🖥️ Windows
1. Download `DICOM_WSI_Deidentifier-windows.zip`.
2. Right-click the ZIP → Properties → tick **Unblock** at the bottom of the
   General tab → OK.
3. Extract the ZIP (File Explorer, 7-Zip, WinRAR), open the folder, and
   double-click `DICOM_WSI_Deidentifier.exe`.
4. If you still see "Windows protected your PC": click **More info**, then
   **Run anyway**.

Optional: move the app folder to a desired location and create a shortcut of DICOM_WSI_Deidentifier.exe

### 🍎 macOS
1. Download the macOS build, unzip it and move `DICOM_WSI_Deidentifier.app` to Applications.
2. Double-click it. You will see a warning; click **Done** (not "Move to
   Trash").
3. Open **System Settings → Privacy & Security**, scroll to **Security**,
   and click **Open Anyway** next to the DICOM_WSI_Deidentifier message.
4. Enter your password or Touch ID, then click **Open**.

## 📝 How to Cite
You can cite the related paper accepted in Archives of Pathology and Laboratory Medicine (link pending).

## Security best practices & key management

The secret key is the one of the most critical component of this tool.
- key strength: do not use simple or short keys (e.g., "12345"). Use a strong, random string of at least 12 characters containing uppercase letters, numbers, and symbols.
- secure storage: never store your secret key in the same folder as your correspondence CSV. Access to both makes it more likely to restore sensitive information.
- key loss: if the key is lost (and the CSV files), you cannot link de-identified files to previously processed ones.
- consistency: make sure to use the same key when processing different parts of the same longitudinal study to maintain temporal relationships between slides.

## Versions

Latest version: 2.0.1
Key changes:
- update app version in the DeidentificationMethod DICOM tag

Previous versions: 
2.0.0
Key changes:
- move from tkinter/pyinstaller to Flet-based application and user interface
- ensure uid generation actually uses the secret_key for reproducible results
- update dependencies: pydicom 2.4.4 => 3.0.2; pillow 10.4.0 => 11.3.0; numpy 1.24.4 => 2.1.1
- versioning system changed

v.2026.05.09:
- Added random secure key by default and criteria to define a strong key
- Modified column name in template (WSI name => Original WSI name) and corresponding handling to match the output correspondence CSV file

_01022026: app launch

## Related projects
Other efforts related to deidentifying medical images include:
- [imageDePHI](https://github.com/DigitalSlideArchive/ImageDePHI) and [WSI DeID](https://github.com/DigitalSlideArchive/DSA-WSI-DeID): workflows built onto the Digital Slide Archive for redacting medical images.
- [dicom-anonymizer](https://github.com/KitwareMedical/dicom-anonymizer): a python tool for deidentifying DICOM files
- [TIO-IKIM medical_image_deidentification](https://github.com/TIO-IKIM/medical_image_deidentification): a python tool for deidentifying DICOM files from radiology and histology (WSI)
