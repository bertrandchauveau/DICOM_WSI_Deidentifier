# DICOM_WSI_Deidentifier

To deidentify DICOM whole slide images in conformance to the DICOM basic application level confidentiality profile

This work is currently under review in a scientific journal. The link to the journal article will be presented when published.

Pathology Departments in their digitization transition are encouraged to adopt the Digital Imaging and Communications in Medicine (DICOM) format for routine diagnosis, leading to a major increase of histopathological image-based research projects using this format. Still, DICOM for whole slide images (WSI) remains an emerging file format, with limited tools currently available for deidentification without coding skills. This project aimed to build an easy-to-use and no-code tool to deidentify DICOM WSI, with feedback on the deidentification process.

This is a Python-based solution to deidentify DICOM WSI in conformance to the DICOM basic application level confidentiality profile (for more information, see https://dicom.nema.org/medical/dicom/current/output/chtml/part15/chapter_e.html).

The solution is provided in 3 ways: 
- a Colab-compatible jupyter notebook for easy testing
- a Python script to be run through Command Line Interface
- a Windows and MacOS executable created using PyInstaller 6.11.1, as such prior coding knowledge is not required
<a target="_blank" href="https://colab.research.google.com/github/bertrandchauveau/DICOM_WSI_Deidentifier/blob/main/DICOM_WSI_Deidentifier.ipynb">
  <img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/>
</a>

The Python script was tested using either a Windows or macOS in a conda virtual environment.
The main dependencies used are:
- Pydicom 2.4.4
- Pandas 2.2.2
- Pillow 10.4.0
- qrcode 8.2
- NumPy 1.24.4 

The Windows executable was tested on either a Windows 10 Professional 22H2 and a Windows 11 Professional 24H2. The MacOS executable was tested on MacOS Sequoia 15.7.4.

The deidentification process creates from scratch the deidentified WSI (no modification of original files) and includes several steps: (i) the removal of the macro/overview image, which includes the label for some scanners, (ii) the removal of the original label, replaced by a QR code image of the deidentified sample ID, (iii) the removal or modifications of the DICOM metadata in all files, and (iv) the addition of three DICOM tags qualifying the deidentification of each file: “patient identity removed”, “deidentification method” and “longitudinal temporal information modified”.

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

The arguments, to be defined through Tkinter user interface are:
- path_to_WSI: the path to the folder containing the sensitive DICOM WSI (as folders or zip)
- path_output: the path where the deidentified WSI will be saved
- path to CSV file: an optional CSV file (separator ";") matching original sample reference (or WSI name) with the desired deidentified reference and WSI name. The header of the columns should be: "WSI name", "Original ID" and "Deidentified ID". See also the provided template.
- secret key: a string secret key to ensure reproducibility in terms of (i) acquisition date shift (+/- 6 months), (ii) modifications of the DICOM Unique Identifiers (UID) and (iii) modification of the sample identifier and file name.
- identifier of reference: whether the deidentified WSI name and sample reference should be based on the original sample identifier or WSI name
- annotations: whether annotations files should be maintained during the process. Default to False. Beware that maintaining the annotation files is against the DICOM basic application level confidentiality profile. You should be sure that the graphic element and associated text of the annotation do not contain sensitive information.
- longitudinal temporal information: whether the date shift should be applied to the original acquisition date/time, as such maintaining the longitudinal temporal information between slides. Default to False, with the use of the date of the deidentification run. If True, in conformance to the Retain Longitudinal Temporal Information Option (see https://dicom.nema.org/medical/dicom/current/output/chtml/part15/sect_E.3.6.html)
- txt file: whether txt files should be created for each deidentified .dcm file, listing DICOM metadata, to verify the integrity of the process

## Usage (Python script):
- considering a Python environment with the required dependencies:
  
```python /path_to/DICOM_WSI_Deidentifier_01022026.py```

## Installation instructions and usage (Windows or MacOS executable):
- end-users must seek the validation of their information technology service management before using the application on an institutional device and only use DICOM originating from a trusted source
- download the DICOMtoSVS.zip file at:

  => Windows: pending
  
  => MacOS: pending
  
- decompress the file in your local disk, ending up with a DICOM_WSI_Deidentifier_XX folder containing a "DICOM_WSI_Deidentifier_XX.exe" file and a "_internal" folder, containing required files to run the executable. Do not separate the "_internal" folder from the exe file. 
- optional: create a desktop shortcut of the .exe file (right-clik, create shortcut)
- when running the .exe file for the first time, Windows will display a warning message "unknown publisher". This is an expected behavior from Windows.
- running the .exe file will launch a command prompt and, a few seconds later, another window to select the arguments for the deidentification process. You should point out the folder where the native DICOM files are (.../native_folder). It is not expected that the selected folder contains other files or folder types.
- A window "Deidentification completed" appears at the end of the process. The command prompt can be closed, after verifying possible warning messages for specific WSI. Deidentified WSI are stored at the defined path_output.

## Security best practices & key management

The secret key is the one of the most critical component of this tool.
- key strength: do not use simple or short keys (e.g., "12345"). Use a strong, random string of at least 12 characters containing uppercase letters, numbers, and symbols.
- secure storage: never store your secret key in the same folder as your correspondence CSV. Access to both makes it more likely to restore sensitive information.
- key loss: if the key is lost (and the CSV files), you cannot link de-identified files to previously processed ones.
- consistency: make sure to use the same key when processing different parts of the same longitudinal study to maintain temporal relationships between slides.

## Versions
Latest version: _01022026

## Related projects
Other efforts related to anonimyzing medical images include:
- imageDePHI and WSI DeID: workflows built onto the Digital Slide Archive for redacting medical images.
- dicom-anonymizer: a python tool for anonymizing DICOM files

