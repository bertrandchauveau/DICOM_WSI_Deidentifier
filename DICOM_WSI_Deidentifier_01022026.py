import os
import shutil
import numpy as np
import zipfile
import natsort
from natsort import os_sorted
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import UID, ExplicitVRLittleEndian, generate_uid
from pydicom.encaps import encapsulate
from pydicom.tag import Tag
import tkinter as tk
from tkinter import filedialog, messagebox
import random
import hashlib
import hmac
import os
import binascii
from pydicom.uid import generate_uid
import qrcode
import pandas as pd
from time import gmtime, strftime
from datetime import datetime, timedelta
import sys

#Keyed Hashing (HMAC)
def anonymize_id(original_id, key):
    # Ensure the original_id is bytes (HMAC works on bytes)
    id_bytes = str(original_id).encode('utf-8')
    
    # Use HMAC with SHA256 (a strong cryptographic hash function)
    # The output digest is a unique, consistent "fingerprint"
    hashed_bytes = hmac.new(key, id_bytes, hashlib.sha256).digest()
    
    # Convert the raw bytes to a readable hex string for the final ID
    # The result will be a 64-character hex string.
    return binascii.hexlify(hashed_bytes).decode('utf-8')

def get_filename_no_ext(path):
    filename_noext_list = []
    filenames = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)) and 'DS_Store' not in f]  #only look at files, not directories #exclude Mac OS files
    for filename in filenames:
        #if not os.path.isdir(path + '/' + filename): 
        (name, ext) = os.path.splitext(filename)
        if not ext:
            filename_noext_list.append(filename)
    return filename_noext_list

def define_barcode_value(ds_native, WSI_name, SECRET_KEY_str='12345678910', correspondence_dict=None, correspondence_option=None):

    #SECRET KEY (Must be kept secret and consistent across all runs)
    SECRET_KEY = SECRET_KEY_str.encode('utf-8')

    #check current reference
    if hasattr(ds_native, 'ContainerIdentifier') and len(ds_native.ContainerIdentifier)!=0:
        reference_ID = ds_native.ContainerIdentifier
    elif hasattr(ds_native, 'PatientID') and len(ds_native.PatientID)!=0:
        reference_ID = ds_native.PatientID       
    elif hasattr(ds_native, 'BarcodeValue') and len(ds_native.BarcodeValue)!=0: #patientID before, not mandatory for original files. But discrepancies between the two for WSI and annotation files when deidentified by Sectra
        reference_ID = ds_native.BarcodeValue
    elif hasattr(ds_native, 'AccessionNumber') and len(ds_native.AccessionNumber)!=0:
        reference_ID = ds_native.AccessionNumber
    else:
        now = strftime("%Y-%m-%d %H:%M:%S", gmtime())
        print(f'No reference ID detected in original image, assigning default as datetime: H{now}')
        reference_ID = 'H'+ now
    
    #check if native DICOM file is already de-identified
    if hasattr(ds_native, 'PatientIdentityRemoved'):
        if ds_native.PatientIdentityRemoved == 'YES':
            print('WARNING: DICOM file already tagged as deidentified, processing it anyway')
            #barcode_value = ds_native.PatientID 
    #create an ANONYMISATION ID or use the correspondence dict
    try: #try to use correspondence dict
        if correspondence_option=="WSI name": 
            barcode_value = correspondence_dict[WSI_name]
        else:
            barcode_value = correspondence_dict[reference_ID] #default to reference ID
    except: #by Keyed Hashing
        if correspondence_option=="WSI name": 
            barcode_value = anonymize_id(WSI_name, SECRET_KEY)
        else:
            barcode_value = anonymize_id(reference_ID, SECRET_KEY) #default to reference ID   
    return barcode_value, reference_ID

def set_attribute(ds, ds_native, attributes):
    for attr in attributes:
        if hasattr(ds_native, attr):
            setattr(ds, attr, getattr(ds_native, attr))


# Define the maximum shift range (e.g., +/- 180 days)
def derive_consistent_date_shift(original_id: str, key: str, MAX_SHIFT_DAYS = 180) -> timedelta:
    key = key.encode("utf-8") #to bytes
    # 1. Generate a patient-consistent seed (HMAC)
    #id_bytes = original_id.encode('utf-8')
    #hmac_digest = hmac.new(key, id_bytes, hashlib.sha256).digest()
    #1. Generate a run-consistent seed
    hmac_digest = hmac.new(key, key, hashlib.sha256).digest()

    # 2. Derive a bounded integer shift value
    # Take the first 4 bytes for 32 bits of entropy (more than enough for 361 possibilities)
    # Convert those 4 bytes to an integer (Big-Endian format)
    N = int.from_bytes(hmac_digest[:4], byteorder='big')
    
    # Use modulo arithmetic to bound the shift. Range: [0, 2 * MAX_SHIFT_DAYS]
    shift_range = 2 * MAX_SHIFT_DAYS + 1 # e.g., 361 days
    bounded_shift = N % shift_range
    
    # Shift the range to be centered around zero (e.g., [-180, 180] days)
    days_to_shift = bounded_shift - MAX_SHIFT_DAYS
    
    return timedelta(days=days_to_shift)

def shift_dicom_date(dicom_datetime_str: str, shift_delta: timedelta, current_date_time, DICOM_DATE_FORMAT = '%Y%m%d') -> str:
    if not dicom_datetime_str:
        return current_date_time

    #if dicom_datetime_str==current_date_time:
    #    return current_date_time
    
    # DICOM can contain date/time up to microseconds and timezone
    #datetime/DT format YYYYMMDDHHMMSS.FFFFFF&ZZXX #https://dicom.nema.org/medical/dicom/current/output/chtml/part05/sect_6.2.html
    # Date (DA) is the first 8 characters: YYYYMMDD
    date_part = dicom_datetime_str[:8]
    #time_part = dicom_datetime_str[8:].split('+', 1)[0]   # HHMMSS.FFFFFF+UTOFFSET (optional) 
    time_and_tz_part = '100000+0000' #default time and time zone

    try:
        # 1. Parse the date part
        original_date = datetime.strptime(date_part, DICOM_DATE_FORMAT).date()
        
        # 2. Apply the shift
        shifted_date = original_date + shift_delta
        
        # 3. Reformat the date and concatenate with the original time/timezone
        shifted_date_str = shifted_date.strftime(DICOM_DATE_FORMAT)
        return shifted_date_str + time_and_tz_part
        
    except ValueError:
        # Handle cases where the string might not be a valid date format
        print(f"Warning: Could not parse date {date_part}. Returning current date/time.")
        return current_date_time

indent_chars = "   "
def my_pretty_str(
        self, indent: int = 0, top_level_only: bool = False
    ) -> str:
        strings = []
        indent_str = self.indent_chars * indent
        nextindent_str = self.indent_chars * (indent + 1)

        # Display file meta, if configured to do so, and have a non-empty one
        if (
            hasattr(self, "file_meta") and self.file_meta
            and pydicom.config.show_file_meta
        ):
            strings.append(f"{'Dataset.file_meta ':-<49}")
            for elem in self.file_meta:
                #with tag_in_exception(elem.tag):
                strings.append(indent_str + repr(elem))
            strings.append(f"{'':-<49}")

        for elem in self:
            #with tag_in_exception(elem.tag):
            if elem.VR == 'SQ':  # a sequence
                strings.append(
                    f"{indent_str}{str(elem.tag)}  {elem.name}  "
                    f"{len(elem.value)} item(s) ---- "
                )
                if not top_level_only:
                    for dataset in elem.value:
                        strings.append(dataset._pretty_str(indent + 1))
                        strings.append(nextindent_str + "---------")
            else:
                # 3. Handle LT (Long Text) - Print full value, with text alignment
                if elem.VR == "LT":
                    elem_desc = repr(elem)
                    try:
                        nb_space = len(elem_desc.split(elem.name, 1)[1].split(elem.VR,1)[0])
                    except:
                        nb_space = 1
                    nb_space = ' ' * nb_space
                    val = str(elem.value)
                    strings.append(f"{indent_str}{elem.tag} {elem.name}{nb_space}{elem.VR}: {val}")
                else:
                    strings.append(indent_str + repr(elem))
        return "\n".join(strings)

        
def anonymize_WSI_dcm_file(ds_native, barcode_value, path_output, num_dcm, current_date_time, SECRET_KEY_str, txt_file, long_temp_inf):
    
    #create all UIDs
    #on the fly based on the original ones
    
    # Create a new DICOM Dataset object
    ds = pydicom.Dataset()
    
    # Add file meta information
    file_meta = pydicom.Dataset()
    file_meta.FileMetaInformationGroupLength = ds_native.file_meta.FileMetaInformationGroupLength
    file_meta.MediaStorageSOPClassUID = ds_native.file_meta.MediaStorageSOPClassUID #constant, WSI related
    file_meta.MediaStorageSOPInstanceUID = generate_uid(entropy_srcs=[str(ds_native.file_meta.MediaStorageSOPInstanceUID)])
    file_meta.TransferSyntaxUID = ds_native.file_meta.TransferSyntaxUID #JPEG Baseline (Process 1) or other
    file_meta.ImplementationClassUID = ds_native.file_meta.ImplementationClassUID if hasattr(ds_native.file_meta, 'ImplementationClassUID') else '1.2.826.0.1.3680043.8.498.1' #pydicom
    ds.file_meta = file_meta
    
    # Add original DICOM metadata if initially present
    attributes = ['SpecificCharacterSet', 'ImageType', 'SOPClassUID', 'Modality', 'Manufacturer', 'ManufacturerModelName', 'VolumetricProperties',
                 'SoftwareVersions', 'ConvolutionKernel', 'AcquisitionDuration', 'InstanceNumber', 'PositionReferenceIndicator',
                 'DimensionOrganizationType', 'SamplesPerPixel', 'PhotometricInterpretation', 'PlanarConfiguration', 'NumberOfFrames',
                 'Rows', 'Columns', 'BitsAllocated', 'BitsStored', 'HighBit', 'PixelRepresentation', 'BurnedInAnnotation', 'RescaleIntercept',
                 'RescaleSlope', 'LossyImageCompression', 'LossyImageCompressionRatio', 'LossyImageCompressionMethod', 'ImagedVolumeWidth',
                 'ImagedVolumeHeight', 'ImagedVolumeDepth', 'TotalPixelMatrixColumns', 'TotalPixelMatrixRows', 'SpecimenLabelInImage',
                 'FocusMethod', 'ExtendedDepthOfField', 'ImageOrientationSlide', 'NumberOfOpticalPaths', 'TotalPixelMatrixFocalPlanes',
                 'PresentationLUTShape', 'InConcatenationNumber', 'ConcatenationFrameOffsetNumber', 'NumberOfFocalPlanes', 'DistanceBetweenFocalPlanes']

    for attr in attributes:
        if hasattr(ds_native, attr):
            setattr(ds, attr, getattr(ds_native, attr))

    #add general DICOM tags
    ds.SOPInstanceUID = generate_uid(entropy_srcs=[str(ds_native.SOPInstanceUID)])
    ds.StudyDate  = ''
    ds.StudyTime  = ''
    if len(barcode_value) <=16:
        ds.AccessionNumber = barcode_value #can't be more than 16 characters, barcode_value is 64
        ds.StudyID = barcode_value #can't be more than 16 characters, barcode_value is 64
    else:
        ds.AccessionNumber = ''
        ds.StudyID = ''
    ds.ReferringPhysicianName = ''
    ds.PatientName = 'anonymous'
    ds.PatientID = barcode_value
    ds.PatientBirthDate = ''
    ds.PatientSex = 'O'
    ds.PatientIdentityRemoved = 'YES'
    ds.DeidentificationMethod = 'DICOM_WSI_Deidentifier_01022026'
    ds.DeviceSerialNumber = 'anonymous'
    ds.StudyInstanceUID = generate_uid(entropy_srcs=[str(ds_native.StudyInstanceUID)])
    ds.SeriesInstanceUID = generate_uid(entropy_srcs=[str(ds_native.SeriesInstanceUID)])
    ds.SeriesNumber = None
    if hasattr(ds_native, 'FrameOfReferenceUID'):
        ds.FrameOfReferenceUID = generate_uid(entropy_srcs=[str(ds_native.FrameOfReferenceUID)])
    ds.ContainerIdentifier = barcode_value
    ds.IssuerOfTheContainerIdentifierSequence = ''
    ds.AcquisitionContextSequence = '' #should be erased because can contain the save path location
    ds.BarcodeValue = barcode_value
    if hasattr(ds_native, 'ConcatenationUID'):
        ds.ConcatenationUID = generate_uid(entropy_srcs=[str(ds_native.ConcatenationUID)])                 
    if hasattr(ds_native, 'SOPInstanceUIDOfConcatenationSource'):
        ds.SOPInstanceUIDOfConcatenationSource = generate_uid(entropy_srcs=[str(ds_native.SOPInstanceUIDOfConcatenationSource)])                 
    ds.LongitudinalTemporalInformationModified = "MODIFIED"
    
    #add shifted datetime or, if unavailable, the current datetime
    #calculate the unique consistent shift depending on barcode_value
    shift = derive_consistent_date_shift(barcode_value, SECRET_KEY_str)
    #Apply the shift
    date_study = ds_native.AcquisitionDateTime if hasattr(ds_native, 'AcquisitionDateTime') and long_temp_inf is True else current_date_time
    ds.AcquisitionDateTime = shift_dicom_date(date_study, shift, current_date_time)
    if not hasattr(ds_native, 'AcquisitionDateTime') and long_temp_inf is True:
        print('No acquisition date/time in the metadata of this WSI, shift will be applied on current date/time')
    
    #add specific sequences
    # Add dimension organization and index sequences
    if hasattr(ds_native, 'DimensionOrganizationSequence') and len(ds_native.DimensionOrganizationSequence)!=0:
        dimension_org_seq_list = []
        for i in range(0, len(ds_native.DimensionOrganizationSequence)):
            dimension_org_seq = pydicom.Dataset()
            dimension_org_seq.DimensionOrganizationUID = generate_uid(entropy_srcs=[str(ds_native.DimensionOrganizationSequence[i].DimensionOrganizationUID)])
            dimension_org_seq_list.append(dimension_org_seq)
        ds.DimensionOrganizationSequence = dimension_org_seq_list

    if hasattr(ds_native, 'DimensionIndexSequence') and len(ds_native.DimensionIndexSequence)!=0:
        dimension_idx_seq_list = []
        for i in range(0, len(ds_native.DimensionIndexSequence)):
            dimension_index_seq = pydicom.Dataset()
            dimension_index_seq.DimensionOrganizationUID = generate_uid(entropy_srcs=[str(ds_native.DimensionIndexSequence[i].DimensionOrganizationUID)])
            #add non uid elements
            attributes_list = ['DimensionIndexPointer', 'FunctionalGroupPointer']
            set_attribute(dimension_index_seq, ds_native.DimensionIndexSequence[i], attributes_list)
            dimension_idx_seq_list.append(dimension_index_seq)
        ds.DimensionIndexSequence = dimension_idx_seq_list
    
    # Add container identifier and type sequences
    if hasattr(ds_native, 'ContainerTypeCodeSequence') and len(ds_native.ContainerTypeCodeSequence)!=0:    
        container_id_seq_list = []
        for i in range(0, len(ds_native.ContainerTypeCodeSequence)):
            container_id_seq = pydicom.Dataset()
            attributes_list = ['CodeValue', 'CodingSchemeDesignator', 'CodeMeaning']
            set_attribute(container_id_seq, ds_native.ContainerTypeCodeSequence[i], attributes_list)
            container_id_seq_list.append(container_id_seq)
        ds.ContainerTypeCodeSequence = container_id_seq_list
        
    # Add specimen description sequence
    specimen_desc_seq = pydicom.Dataset()
    specimen_desc_seq.SpecimenIdentifier = barcode_value
    specimen_desc_seq.SpecimenUID = generate_uid(entropy_srcs=[str(ds_native.SpecimenDescriptionSequence[0].SpecimenUID)])
    specimen_desc_seq.IssuerOfTheSpecimenIdentifierSequence = ''
    specimen_desc_seq.SpecimenPreparationSequence = ''
    ds.SpecimenDescriptionSequence = [specimen_desc_seq]

    # Add total pixel matrix origin sequence
    pixel_matrix_origin_seq = pydicom.Dataset()
    attributes_list = ['XOffsetInSlideCoordinateSystem', 'YOffsetInSlideCoordinateSystem']
    set_attribute(pixel_matrix_origin_seq, ds_native.TotalPixelMatrixOriginSequence[0], attributes_list)
    ds.TotalPixelMatrixOriginSequence = [pixel_matrix_origin_seq]

    # Add optical path sequence
    if hasattr(ds_native, 'OpticalPathSequence') and len(ds_native.OpticalPathSequence)!=0:
        optical_path_seq_list = []
        for i in range(0, len(ds_native.OpticalPathSequence)):
            optical_path_seq = pydicom.Dataset()
            if hasattr(ds_native.OpticalPathSequence[i], 'LightPathFilterPassThroughWavelength'):
                optical_path_seq.LightPathFilterPassThroughWavelength = ds_native.OpticalPathSequence[i].LightPathFilterPassThroughWavelength
            if hasattr(ds_native.OpticalPathSequence[i], 'ImagePathFilterPassThroughWavelength'):
                optical_path_seq.ImagePathFilterPassThroughWavelength = ds_native.OpticalPathSequence[i].ImagePathFilterPassThroughWavelength
            
            # Add illumination type code sequence
            illumination_type_code_seq = pydicom.Dataset()
            attributes_list = ['CodeValue', 'CodingSchemeDesignator', 'CodeMeaning']
            set_attribute(illumination_type_code_seq, ds_native.OpticalPathSequence[i].IlluminationTypeCodeSequence[0], attributes_list)    
            optical_path_seq.IlluminationTypeCodeSequence = [illumination_type_code_seq]
            
            # Add lenses code sequence
            if hasattr(ds_native.OpticalPathSequence[i], 'LensesCodeSequence'):
                lenses_code_seq = pydicom.Dataset()
                attributes_list = ['CodeValue', 'CodingSchemeDesignator', 'CodeMeaning']
                set_attribute(lenses_code_seq, ds_native.OpticalPathSequence[i].LensesCodeSequence[0], attributes_list)          
                optical_path_seq.LensesCodeSequence = [lenses_code_seq]
            
            if hasattr(ds_native.OpticalPathSequence[i], 'IlluminationWaveLength'):
                optical_path_seq.IlluminationWaveLength = ds_native.OpticalPathSequence[i].IlluminationWaveLength
            # Add ICC profile (simplified as we don't have the actual data)
            if hasattr(ds_native.OpticalPathSequence[i], 'ICCProfile'):
                optical_path_seq.ICCProfile = ds_native.OpticalPathSequence[i].ICCProfile
            
            # Add illuminator type code sequence
            if hasattr(ds_native.OpticalPathSequence[i], 'IlluminatorTypeCodeSequence'):
                illuminator_type_code_seq = pydicom.Dataset()
                attributes_list = ['CodeValue', 'CodingSchemeDesignator', 'CodeMeaning']
                set_attribute(illuminator_type_code_seq, ds_native.OpticalPathSequence[i].IlluminatorTypeCodeSequence[0], attributes_list)          
                optical_path_seq.IlluminatorTypeCodeSequence = [illuminator_type_code_seq]
            
            # Add illumination color code sequence
            if hasattr(ds_native.OpticalPathSequence[i], 'IlluminationColorCodeSequence'):
                illumination_color_code_seq = pydicom.Dataset()
                attributes_list = ['CodeValue', 'CodingSchemeDesignator', 'CodeMeaning']
                set_attribute(illumination_color_code_seq, ds_native.OpticalPathSequence[i].IlluminationColorCodeSequence[0], attributes_list)          
                optical_path_seq.IlluminationColorCodeSequence = [illumination_color_code_seq]
    
            # Add optical path identifier and objective lens power
            attributes_list = ['OpticalPathIdentifier', 'OpticalPathDescription', 'ObjectiveLensPower']
            set_attribute(optical_path_seq, ds_native.OpticalPathSequence[i], attributes_list) 

            # Add Palette Color Lookup Table Sequence
            if hasattr(ds_native.OpticalPathSequence[i], 'PaletteColorLookupTableSequence'):
                palette_color_LUT_seq = pydicom.Dataset()
                attributes_list = ['RedPaletteColorLookupTableDescriptor', 'GreenPaletteColorLookupTableDescriptor', 'BluePaletteColorLookupTableDescriptor',
                                  'SegmentedRedPaletteColorLookupTableData', 'SegmentedGreenPaletteColorLookupTableData', 'SegmentedBluePaletteColorLookupTableData']
                set_attribute(palette_color_LUT_seq, ds_native.OpticalPathSequence[i].PaletteColorLookupTableSequence[0], attributes_list)         
                optical_path_seq.PaletteColorLookupTableSequence = [palette_color_LUT_seq]
                
            optical_path_seq_list.append(optical_path_seq)
        ds.OpticalPathSequence = optical_path_seq_list

    # Add shared functional groups sequence/tiled_full
    if hasattr(ds_native, 'SharedFunctionalGroupsSequence') and len(ds_native.SharedFunctionalGroupsSequence)!=0:
        shared_func_groups_seq = pydicom.Dataset()
        ds.SharedFunctionalGroupsSequence = [shared_func_groups_seq]
        
        # Add pixel measures sequence
        if hasattr(ds_native.SharedFunctionalGroupsSequence[0], 'PixelMeasuresSequence') and len(ds_native.SharedFunctionalGroupsSequence[0].PixelMeasuresSequence)!=0:  
            pixel_measures_seq_list = []
            for y in range(0, len(ds_native.SharedFunctionalGroupsSequence[0].PixelMeasuresSequence)):
                pixel_measures_seq = pydicom.Dataset()
                attributes_list = ['SliceThickness', 'SpacingBetweenSlices', 'PixelSpacing']
                set_attribute(pixel_measures_seq, ds_native.SharedFunctionalGroupsSequence[0].PixelMeasuresSequence[y], attributes_list) 
                pixel_measures_seq_list.append(pixel_measures_seq)
            shared_func_groups_seq.PixelMeasuresSequence = pixel_measures_seq_list
            
        # Add whole slide microscopy image frame type sequence
        if hasattr(ds_native.SharedFunctionalGroupsSequence[0], 'WholeSlideMicroscopyImageFrameTypeSequence') and len(ds_native.SharedFunctionalGroupsSequence[0].WholeSlideMicroscopyImageFrameTypeSequence)!=0:  
            image_frame_type_seq_list = []
            for y in range(0, len(ds_native.SharedFunctionalGroupsSequence[0].WholeSlideMicroscopyImageFrameTypeSequence)):
                image_frame_type_seq = pydicom.Dataset()
                if hasattr(ds_native.SharedFunctionalGroupsSequence[0].WholeSlideMicroscopyImageFrameTypeSequence[y], 'FrameType'):
                    image_frame_type_seq.FrameType = ds_native.SharedFunctionalGroupsSequence[0].WholeSlideMicroscopyImageFrameTypeSequence[y].FrameType
                image_frame_type_seq_list.append(image_frame_type_seq)
            shared_func_groups_seq.WholeSlideMicroscopyImageFrameTypeSequence = image_frame_type_seq_list
        
        # Add optical path identification sequence
        if hasattr(ds_native.SharedFunctionalGroupsSequence[0], 'OpticalPathIdentificationSequence') and len(ds_native.SharedFunctionalGroupsSequence[0].OpticalPathIdentificationSequence)!=0:        
            optical_path_id_seq_list = []
            for y in range(0, len(ds_native.SharedFunctionalGroupsSequence[0].OpticalPathIdentificationSequence)):            
                optical_path_id_seq = pydicom.Dataset()
                if hasattr(ds_native.SharedFunctionalGroupsSequence[0].OpticalPathIdentificationSequence[y], 'OpticalPathIdentifier'):
                    optical_path_id_seq.OpticalPathIdentifier = ds_native.SharedFunctionalGroupsSequence[0].OpticalPathIdentificationSequence[y].OpticalPathIdentifier
                optical_path_id_seq_list.append(optical_path_id_seq)
            shared_func_groups_seq.OpticalPathIdentificationSequence = optical_path_id_seq_list   

    #tiled_sparse
    if hasattr(ds_native, 'PerFrameFunctionalGroupsSequence') and len(ds_native.PerFrameFunctionalGroupsSequence)!=0:
        perframe_func_groups_seq_list = []
        for i in range(0, len(ds_native.PerFrameFunctionalGroupsSequence)):
            perframe_func_groups_seq = pydicom.Dataset()
            if hasattr(ds_native.PerFrameFunctionalGroupsSequence[i], 'FrameContentSequence') and len(ds_native.PerFrameFunctionalGroupsSequence[i].FrameContentSequence)!=0:
                frame_content_seq_list = []
                for j in range(0, len(ds_native.PerFrameFunctionalGroupsSequence[i].FrameContentSequence)):
                    frame_content_seq = pydicom.Dataset()
                    attributes_list = ['FrameAcquisitionDuration', 'DimensionIndexValues']
                    set_attribute(frame_content_seq, ds_native.PerFrameFunctionalGroupsSequence[i].FrameContentSequence[j], attributes_list) 
                    #date/time attributes
                    FrameAcquisitionDateTime = ds_native.PerFrameFunctionalGroupsSequence[i].FrameContentSequence[j].FrameAcquisitionDateTime if hasattr(ds_native.PerFrameFunctionalGroupsSequence[i].FrameContentSequence[j], 'FrameAcquisitionDateTime') and long_temp_inf is True else current_date_time
                    frame_content_seq.FrameAcquisitionDateTime = shift_dicom_date(FrameAcquisitionDateTime, shift, current_date_time)
                    FrameReferenceDateTime = ds_native.PerFrameFunctionalGroupsSequence[i].FrameContentSequence[j].FrameReferenceDateTime if hasattr(ds_native.PerFrameFunctionalGroupsSequence[i].FrameContentSequence[j], 'FrameReferenceDateTime') and long_temp_inf is True else current_date_time
                    frame_content_seq.FrameReferenceDateTime = shift_dicom_date(FrameReferenceDateTime, shift, current_date_time)      
                    frame_content_seq_list.append(frame_content_seq)
                perframe_func_groups_seq.FrameContentSequence = frame_content_seq_list
            
            if hasattr(ds_native.PerFrameFunctionalGroupsSequence[i], 'PlanePositionSlideSequence') and len(ds_native.PerFrameFunctionalGroupsSequence[i].PlanePositionSlideSequence)!=0:
                plane_pos_slide_seq_list = []
                for j in range(0, len(ds_native.PerFrameFunctionalGroupsSequence[i].PlanePositionSlideSequence)):
                    plane_pos_slide_seq = pydicom.Dataset()
                    attributes_list = ['XOffsetInSlideCoordinateSystem', 'YOffsetInSlideCoordinateSystem', 'ZOffsetInSlideCoordinateSystem',
                                      'ColumnPositionInTotalImagePixelMatrix', 'RowPositionInTotalImagePixelMatrix']
                    set_attribute(plane_pos_slide_seq, ds_native.PerFrameFunctionalGroupsSequence[i].PlanePositionSlideSequence[j], attributes_list) 
                    plane_pos_slide_seq_list.append(plane_pos_slide_seq)            
                perframe_func_groups_seq.PlanePositionSlideSequence = plane_pos_slide_seq_list
            perframe_func_groups_seq_list.append(perframe_func_groups_seq)
            ds.PerFrameFunctionalGroupsSequence = perframe_func_groups_seq_list
    
    #add pixel data
    if 'LABEL' in ds_native.ImageType:
        #replace with a deidentified QR_code
        label_img = qrcode.make(barcode_value)
        label_array = np.asarray(label_img)*255 #bool=>int
        label_rgb_array = np.stack((label_array,)*3, axis=-1).astype(np.uint8)
        ds.PixelData = label_rgb_array.tobytes() #no compression
        #https://pydicom.github.io/pydicom/stable/auto_examples/image_processing/plot_downsize_image.html#sphx-glr-auto-examples-image-processing-plot-downsize-image-py
        #https://pydicom.github.io/pydicom/stable/guides/user/image_data_compression.html
        ds.file_meta.TransferSyntaxUID = '1.2.840.10008.1.2.1' 	#Explicit VR Little Endian 
        ds.DimensionOrganizationType = "TILED_FULL"
        ds.SamplesPerPixel = 3
        ds.PhotometricInterpretation = 'RGB'
        ds.PlanarConfiguration = 0
        ds.NumberOfFrames = 1
        ds.Rows = label_rgb_array.shape[0]
        ds.Columns = label_rgb_array.shape[1]
        ds.TotalPixelMatrixRows = label_rgb_array.shape[0]
        ds.TotalPixelMatrixColumns = label_rgb_array.shape[1]        
        ds.BitsAllocated = 8
        ds.BitsStored = 8
        ds.HighBit = 7
        ds.PixelRepresentation = 0
        ds.BurnedInAnnotation = 'NO'
        ds.LossyImageCompression = '00'   
    else:
        ds.PixelData = ds_native.PixelData
    
    #avoid some warnings
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    
    # Save the dataset to a file
    x = '0000'
    ds.save_as(path_output+'/'+barcode_value+f'/i{str(int(num_dcm) + 1).zfill(len(x))},0000b.dcm', write_like_original=False) #to add preamble DICOM    
    #add optional txt file
    if txt_file is True:
        ds_print = my_pretty_str(ds)
        with open(os.path.join(path_output, 'txt_files', barcode_value) + '/' + f'/i{str(int(num_dcm) + 1).zfill(len(x))},0000b.txt', 'w') as f:
            f.write(ds_print)
    
def anonymize_annotation_dcm_file(ds_native, barcode_value, path_output, num_dcm, current_date_time, SECRET_KEY_str, txt_file, long_temp_inf):
    # Create a new DICOM Dataset object
    ds = pydicom.Dataset()
    
    # Add file meta information
    file_meta = pydicom.Dataset()
    file_meta.FileMetaInformationGroupLength = ds_native.file_meta.FileMetaInformationGroupLength
    file_meta.MediaStorageSOPClassUID = ds_native.file_meta.MediaStorageSOPClassUID #constant, annotation: Color Softcopy Presentation State Storage
    file_meta.MediaStorageSOPInstanceUID = generate_uid(entropy_srcs=[str(ds_native.file_meta.MediaStorageSOPInstanceUID)])
    file_meta.TransferSyntaxUID = ds_native.file_meta.TransferSyntaxUID #Explicit VR Little Endian
    file_meta.ImplementationClassUID = ds_native.file_meta.ImplementationClassUID if hasattr(ds_native.file_meta, 'ImplementationClassUID') else '1.2.826.0.1.3680043.8.498.1' #pydicom
    ds.file_meta = file_meta
    
    # Add DICOM metadata
    if hasattr(ds_native, 'SpecificCharacterSet'):
        if ds_native.SpecificCharacterSet=="ISO IR 192": #misspelling in some IDS7/Sectra versions
            ds.SpecificCharacterSet = "ISO_IR 192"
        else:
            ds.SpecificCharacterSet = ds_native.SpecificCharacterSet

    # Add original DICOM metadata if initially present
    attributes = ['SOPClassUID', 'Modality', 'Manufacturer', 'SoftwareVersions', 'InstanceNumber', 'ContentLabel', 'ContentDescription']
    #'PresentationCreationDate', 'PresentationCreationTime' removed
    
    for attr in attributes:
        if hasattr(ds_native, attr):
            if attr=='ContentLabel':
                setattr(ds, attr, getattr(ds_native, attr).upper()) #Code String must be uppercase characters, some versions of IDS7/Sectra returns lower case characters
            else:    
                setattr(ds, attr, getattr(ds_native, attr))
            
    ds.SOPInstanceUID = generate_uid(entropy_srcs=[str(ds_native.SOPInstanceUID)])
    ds.StudyDate  = ''
    ds.StudyTime  = ''
    if len(barcode_value)<=16:
        ds.AccessionNumber = barcode_value #can't be more than 16 characters, barcode_value is 64
        ds.StudyID = barcode_value #can't be more than 16 characters, barcode_value is 64
    else:
        ds.AccessionNumber = ''
        ds.StudyID = ''
    ds.ReferringPhysicianName = ''
    ds.PatientName = 'anonymous'
    ds.PatientID = barcode_value
    ds.PatientBirthDate = ''
    ds.PatientSex = 'O'
    ds.PatientIdentityRemoved = 'YES'
    ds.DeidentificationMethod = 'DICOM_WSI_Deidentifier_01022026'
    ds.SeriesInstanceUID = generate_uid(entropy_srcs=[str(ds_native.SeriesInstanceUID)])
    ds.SeriesNumber = None
    ds.ContentCreatorName = ''
    ds.ContainerIdentifier = barcode_value
    ds.BarcodeValue = barcode_value
    ds.LongitudinalTemporalInformationModified = "MODIFIED"
    
    #add shifted datetime or, if unavailable, the current datetime
    #calculate the unique consistent shift depending on barcode_value
    shift = derive_consistent_date_shift(barcode_value, SECRET_KEY_str)
    #Apply the shift
    date_study = ds_native.AcquisitionDateTime if hasattr(ds_native, 'AcquisitionDateTime') and long_temp_inf is True else current_date_time
    ds.AcquisitionDateTime = shift_dicom_date(date_study, shift, current_date_time)
    if not hasattr(ds_native, 'AcquisitionDateTime') and long_temp_inf is True:
        print('No acquisition date/time in the metadata of this WSI, shift will be applied on current date/time')
    
    #Referenced Series Sequence
    if hasattr(ds_native, 'ReferencedSeriesSequence') and len(ds_native.ReferencedSeriesSequence)!=0:    
        ref_series_seq_list = []
        for i in range(0, len(ds_native.ReferencedSeriesSequence)):
            ref_series_seq = pydicom.Dataset()
            if hasattr(ds_native.ReferencedSeriesSequence[i], 'SeriesInstanceUID'):
                ref_series_seq.SeriesInstanceUID = generate_uid(entropy_srcs=[str(ds_native.ReferencedSeriesSequence[i].SeriesInstanceUID)])
            if hasattr(ds_native.ReferencedSeriesSequence[i], 'ReferencedReferenceImageSequence'):
                ref_series_seq.ReferencedReferenceImageSequence = []
            ref_series_seq_list.append(ref_series_seq)
        ds.ReferencedSeriesSequence = ref_series_seq_list

    #Graphic Annotation Sequence
    if hasattr(ds_native, 'GraphicAnnotationSequence') and len(ds_native.GraphicAnnotationSequence)!=0:    
        graph_anot_seq_list = []
        for i in range(0, len(ds_native.GraphicAnnotationSequence)):
            graph_anot_seq = pydicom.Dataset()
            if hasattr(ds_native.GraphicAnnotationSequence[i], 'GraphicLayer'):
                graph_anot_seq.GraphicLayer = ds_native.GraphicAnnotationSequence[i].GraphicLayer.upper() #Code String must be uppercase characters, some versions of IDS7/Sectra returns lower case characters
            if hasattr(ds_native.GraphicAnnotationSequence[i], 'TextObjectSequence') and len(ds_native.GraphicAnnotationSequence[i].TextObjectSequence)!=0:    
                text_obj_seq_list = []
                for y in range(0, len(ds_native.GraphicAnnotationSequence[i].TextObjectSequence)):
                    text_obj_seq = pydicom.Dataset()
                    attributes_list = ['AnchorPointAnnotationUnits', 'UnformattedTextValue', 'AnchorPoint', 'AnchorPointVisibility']
                    set_attribute(text_obj_seq, ds_native.GraphicAnnotationSequence[i].TextObjectSequence[y], attributes_list)                  
                    text_obj_seq_list.append(text_obj_seq)
                graph_anot_seq.TextObjectSequence = text_obj_seq_list
            if hasattr(ds_native.GraphicAnnotationSequence[i], 'GraphicObjectSequence') and len(ds_native.GraphicAnnotationSequence[i].GraphicObjectSequence)!=0:      
                graph_obj_seq_list = []
                for y in range(0, len(ds_native.GraphicAnnotationSequence[i].GraphicObjectSequence)):
                    graph_obj_seq = pydicom.Dataset()
                    attributes_list = ['GraphicAnnotationUnits', 'GraphicDimensions', 'NumberOfGraphicPoints', 'GraphicData', 'GraphicType',
                                      'GraphicFilled']
                    set_attribute(graph_obj_seq, ds_native.GraphicAnnotationSequence[i].GraphicObjectSequence[y], attributes_list)                      
                    graph_obj_seq_list.append(graph_obj_seq)
                graph_anot_seq.GraphicObjectSequence = graph_obj_seq_list  
            graph_anot_seq_list.append(graph_anot_seq)
            ds.GraphicAnnotationSequence = graph_anot_seq_list
    
    #Displayed area sequence
    if hasattr(ds_native, 'DisplayedAreaSelectionSequence') and len(ds_native.DisplayedAreaSelectionSequence)!=0:    
        area_selection_seq_list = []
        for i in range(0, len(ds_native.DisplayedAreaSelectionSequence)):
            area_selection_seq = pydicom.Dataset()
            attributes_list = ['PixelOriginInterpretation', 'DisplayedAreaTopLeftHandCorner', 'DisplayedAreaBottomRightHandCorner',
                              'PresentationSizeMode', 'PresentationPixelAspectRatio']
            set_attribute(area_selection_seq, ds_native.DisplayedAreaSelectionSequence[i], attributes_list)   
            area_selection_seq_list.append(area_selection_seq)
        ds.DisplayedAreaSelectionSequence = area_selection_seq_list
    
    #Graphic Layer sequence
    if hasattr(ds_native, 'GraphicLayerSequence') and len(ds_native.GraphicLayerSequence)!=0:    
        graph_layer_seq_list = []
        for i in range(0, len(ds_native.GraphicLayerSequence)):
            graph_layer_seq = pydicom.Dataset()
            attributes_list = ['GraphicLayer', 'GraphicLayerOrder']
            for attr in attributes_list:
                if hasattr(ds_native.GraphicLayerSequence[i], attr):
                    if attr=='GraphicLayer':
                        setattr(graph_layer_seq, attr, getattr(ds_native.GraphicLayerSequence[i], attr).upper()) #Code String must be uppercase characters, some versions of IDS7/Sectra returns lower case characters
                    else:    
                        setattr(graph_layer_seq, attr, getattr(ds_native.GraphicLayerSequence[i], attr))
            graph_layer_seq_list.append(graph_layer_seq)
        ds.GraphicLayerSequence = graph_layer_seq_list
        
    # Save the dataset to a file
    x = '0000'
    ds.save_as(path_output+'/'+barcode_value+f'/i{str(int(num_dcm) + 1).zfill(len(x))},0000b_graphics.dcm', write_like_original=False)
    #add optional txt file
    if txt_file is True:
        ds_print = my_pretty_str(ds)
        with open(os.path.join(path_output, 'txt_files', barcode_value) + '/' + f'/i{str(int(num_dcm) + 1).zfill(len(x))},0000b_graphics.txt', 'w') as f:
            f.write(ds_print)
    
    
def anonymize_DICOM_WSI(path_to_dcm, WSI_name, path_output, current_date_time, SECRET_KEY_str='12345678910', correspondence_dict=None, correspondence_option=None, annotations=False, txt_file=True, long_temp_inf=False):
    #long_temp_inf longitudinal temporal information
    
    #identify all dcm files
    dcm_files_list = [f for f in os.listdir(path_to_dcm+'/'+WSI_name) if f.endswith('.dcm')]
    dcm_files_list = os_sorted(dcm_files_list)
    #loop through all DICOM files, load DICOM file and detect ImageType
    i=0
    barcode_value_list = []
    reference_ID_list = []
    for num_dcm in range(0, len(dcm_files_list)):
        ds_native = pydicom.dcmread(path_to_dcm+'/'+WSI_name+'/'+dcm_files_list[num_dcm], force=True)
        #define barcode_value
        barcode_value, reference_ID = define_barcode_value(ds_native=ds_native, 
                                                           SECRET_KEY_str=SECRET_KEY_str,
                                                           WSI_name=WSI_name,
                                                           correspondence_dict=correspondence_dict,
                                                           correspondence_option=correspondence_option)
        barcode_value_list.append(barcode_value)
        reference_ID_list.append(reference_ID)
        #create output_folder
        os.makedirs(path_output+'/'+barcode_value, exist_ok=True)
        if txt_file is True:
            os.makedirs(os.path.join(path_output, 'txt_files', barcode_value), exist_ok=True)
        
        #check if dcm file is an annotation or an WSI-related image file
        if hasattr(ds_native.file_meta, 'MediaStorageSOPClassUID'):
            if ds_native.file_meta.MediaStorageSOPClassUID == '1.2.840.10008.5.1.4.1.1.77.1.6': #VL Whole Slide Microscopy Image Storage
                if hasattr(ds_native, 'ImageType'): #otherwise, could be an annotation file
                    image_type = ds_native.ImageType
                    if 'VOLUME' in image_type or 'LABEL' in image_type or 'THUMBNAIL' in image_type: #discard OVERVIEW that could contain the LABEL
                        anonymize_WSI_dcm_file(ds_native = ds_native,
                                               barcode_value = barcode_value,        
                                               path_output = path_output, 
                                               num_dcm=num_dcm,
                                               current_date_time = current_date_time,
                                               SECRET_KEY_str = SECRET_KEY_str,
                                               txt_file = txt_file,
                                               long_temp_inf = long_temp_inf)
                        num_dcm+=1
                        i+=1
            if ds_native.file_meta.MediaStorageSOPClassUID == '1.2.840.10008.5.1.4.1.1.11.2' and annotations is True: #Color Softcopy Presentation State Storage #sectra's annotations are stored that way
                anonymize_annotation_dcm_file(ds_native = ds_native,
                                              barcode_value = barcode_value,        
                                              path_output = path_output, 
                                              num_dcm=num_dcm,
                                              current_date_time = current_date_time,
                                              SECRET_KEY_str = SECRET_KEY_str,
                                              txt_file = txt_file,
                                              long_temp_inf = long_temp_inf)
                num_dcm+=1
                i+=1
        
    if i >0: #at least one file anonymized
        print(f'Slide {WSI_name} deidentified under the name {barcode_value}')
        #check if multiple barcode_values detected for the folder
        barcode_value = np.unique(barcode_value_list).tolist()
        reference_ID = np.unique(reference_ID_list).tolist()
        if len(barcode_value) > 1:
            print(f"WARNING: Multiple barcodes identified for slide: {WSI_name}: barcode_value")
    else:
        print(f'No valid dcm file to anonymize for slide {WSI_name}')

    return ', '.join(barcode_value),  ', '.join(reference_ID) #the one barcode_value if one, multiple if detected so

    
def batch_DICOM_WSI_anonymization(path_to_WSI, path_output, current_date_time, SECRET_KEY_str='12345678910', correspondence_dict=None, correspondence_option=None, annotations=False, txt_file=True, long_temp_inf=False):
    WSI_zip_list = [f for f in os.listdir(path_to_WSI) if f.endswith('.zip')]
    #unzip if needed
    if len(WSI_zip_list) > 0:
        print(f'Detecting {len(WSI_zip_list)} zip folers, unzipping them')
        for WSI in WSI_zip_list:
            with zipfile.ZipFile(path_to_WSI + '/' + WSI, 'r') as zip_ref:
                zip_ref.extractall(path_to_WSI + '/' + WSI[:-4])  #same name, just without the .zip extension 
    #list all potential DICOM folders
    WSI_dir = [f for f in os.listdir(path_to_WSI) if 'DS_Store' not in f and 'MACOSX' not in f and os.path.isdir(path_to_WSI+'/'+f)] #exclude Mac OS files other non directory
    WSI_dir = os_sorted(WSI_dir)
    print(f'Number of potential WSI is: {len(WSI_dir)}')
    if len(WSI_dir)==0:
        print('No detected DICOM WSI to convert, please point to a folder containing either one or several unzipped DICOM folders or one or several zipped DICOM folders.')
    #define output_path
    if not os.path.exists(path_output):
        os.mkdir(path_output)
    if not os.path.exists(os.path.join(path_output, 'txt_files')) and txt_file is True:
        os.mkdir(os.path.join(path_output, 'txt_files'))

    results_cor_dict = {}
    for WSI_name in WSI_dir:
        #check if dcm files
        dcm_files_list = [f for f in os.listdir(path_to_WSI+'/'+WSI_name) if f.endswith('.dcm')]
        dcm_files_list = os_sorted(dcm_files_list)
        #handling cases where dicom files do not have the .dcm extension (=> DICOM conversion with some SlideMaster versions by 3DHistech does not add the .dcm extension to converted files)
        if len(dcm_files_list)==0: #no dcm files detected
            print(f'No .dcm file detected for folder {WSI_name}')
            filename_noext_list = get_filename_no_ext(path_to_WSI+'/'+WSI_name)
            if len(filename_noext_list)!=0: #if files without extension are identified, try to add the .dcm extension to be handled like it
                print('Files without extension present. Do the DICOM files originate from a conversion by SlideMaster? Trying to rename files to add the extension.')
                for filename in filename_noext_list:
                    os.rename(path_to_WSI+'/'+WSI_name + '/' + filename, path_to_WSI+'/'+WSI_name + '/' + filename + '.dcm')
                #anonymize WSI
                barcode_value, reference_ID = anonymize_DICOM_WSI(path_to_dcm = path_to_WSI, 
                                                                    WSI_name = WSI_name, 
                                                                    path_output = path_output, 
                                                                    SECRET_KEY_str = SECRET_KEY_str,
                                                                    correspondence_dict = correspondence_dict,
                                                                    correspondence_option = correspondence_option,
                                                                    current_date_time = current_date_time,
                                                                    annotations = annotations,
                                                                    txt_file = txt_file,
                                                                    long_temp_inf = long_temp_inf)  
                results_cor_dict[WSI_name] = [reference_ID, barcode_value]
            else:
                print(f'No identified file to convert, skipping folder {WSI_name}')
        else:
            #anonymize WSI
            barcode_value, reference_ID = anonymize_DICOM_WSI(path_to_dcm = path_to_WSI, 
                                                                WSI_name = WSI_name, 
                                                                path_output = path_output, 
                                                                SECRET_KEY_str = SECRET_KEY_str,
                                                                correspondence_dict = correspondence_dict, 
                                                                correspondence_option = correspondence_option,
                                                                current_date_time = current_date_time,
                                                                annotations = annotations,
                                                                txt_file = txt_file,
                                                                long_temp_inf = long_temp_inf)
            results_cor_dict[WSI_name] = [reference_ID, barcode_value]
                            
    #convert resulting correspondence dictionary to a csv file and save it to path_output
    results_cor_df = pd.DataFrame.from_dict(results_cor_dict, orient="index", columns=["Original ID", "Deidentified ID"])
    results_cor_df.index.name = 'Original WSI name'
    results_cor_df.reset_index(inplace=True)
    results_cor_df.to_csv(path_output+'/correspondence_output.csv', sep=';', index=False)
    

def main():
    root = tk.Tk()
    root.withdraw()  # Hide the root window

    def select_folder():
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            path_entry.delete(0, tk.END)
            path_entry.insert(0, folder_selected)

    def select_folder2():
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            path_entry2.delete(0, tk.END)
            path_entry2.insert(0, folder_selected)
            
    def select_file():
        # Use askopenfilename and specify the file types
        file_selected = filedialog.askopenfilename(
            title="Select a CSV file",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if file_selected:
            path_entry3.delete(0, tk.END)
            path_entry3.insert(0, file_selected)

    def run_deidentification():
        path_to_wsi_folder = path_entry.get()
        path_output = path_entry2.get()
        try:
            path_to_csv = path_entry3.get()
        except:
            path_to_csv = None
            print('No csv file provided.')
        SECRET_KEY_str = text_var.get()
        correspondence_option = id_choice_var.get()
        annotations = annotations_var.get()
        long_temp = long_temp_var.get()
        txt_file = txt_var.get()

        if not os.path.isdir(path_to_wsi_folder):
            messagebox.showerror("Error", "Invalid folder path for input WSI")
            return
        if not os.path.isdir(path_output):
            messagebox.showerror("Error", "Invalid folder path for deidentified/output WSI")
            return

        # Close the window before running the conversion
        window.destroy()

        #get correspondence dict
        try:
            correspondence_df = pd.read_csv(path_to_csv, sep=";")
            correspondence_dict = dict(zip(correspondence_df[correspondence_option], correspondence_df['Deidentified ID']))
        except:
            correspondence_dict = None
            if path_to_csv is not None:
                print('No correspondence file detected.')
        #correspondence_dict = {'abc':'def'}
        
        #get current date/time
        current_date_time = datetime.now().strftime('%Y%m%d%H%M%S+0000')
        print(f'Current date/time is: {current_date_time}')
        print(f'WSI deidentification will be based on {correspondence_option}')
        #launch deidentification
        batch_DICOM_WSI_anonymization(path_to_WSI = path_to_wsi_folder, 
                                      path_output = path_output, 
                                      SECRET_KEY_str = SECRET_KEY_str, 
                                      correspondence_dict = correspondence_dict, #basé sur la référence matérielle ou le nom de la WSI
                                      correspondence_option = correspondence_option,
                                      current_date_time = current_date_time,
                                      annotations = annotations,
                                      txt_file = txt_file,
                                      long_temp_inf = long_temp)
        
        messagebox.showinfo("Success", "Deidentification completed")
        sys.exit()  #quit python when done

    # Create the main window
    #window = tk.Tk()
    window = tk.Toplevel()
    window.title("DICOM WSI Deidentifier")
            
    tk.Label(window, text="Path to WSI folder:").grid(row=0, column=0, padx=10, pady=10)
    path_entry = tk.Entry(window, width=50)
    path_entry.grid(row=0, column=1, padx=10, pady=10)
    tk.Button(window, text="Browse...", command=select_folder).grid(row=0, column=2, padx=10, pady=10)

    tk.Label(window, text="Output folder:").grid(row=1, column=0, padx=10, pady=10)
    path_entry2 = tk.Entry(window, width=50)
    path_entry2.grid(row=1, column=1, padx=10, pady=10)
    tk.Button(window, text="Browse...", command=select_folder2).grid(row=1, column=2, padx=10, pady=10)

    tk.Label(window, text="Path to a CSV file with desired correspondence (optional):").grid(row=2, column=0, padx=10, pady=10)
    path_entry3 = tk.Entry(window, width=50)
    path_entry3.grid(row=2, column=1, padx=10, pady=10)
    tk.Button(window, text="Browse...", command=select_file).grid(row=2, column=2, padx=10, pady=10)

    text_var = tk.StringVar(value="Enter a secret key here")
    tk.Label(window, text="Enter a secret key (keep it for reproducible results):").grid(row=3, column=0, sticky="w", padx=10, pady=5)
    text_entry = tk.Entry(window, textvariable=text_var, width=30)
    text_entry.grid(row=3, column=1, padx=10, pady=5)

    id_choice_var = tk.StringVar(value="Reference ID")
    tk.Label(window, text="Select the ID which will be used as reference:").grid(row=4, column=0, sticky="w", padx=10, pady=5)
    tk.Radiobutton(window, text="WSI name/folder name", variable=id_choice_var, 
                   value="WSI name").grid(row=4, column=1, sticky="w")
    tk.Radiobutton(window, text="Sample ID (within DICOM metadata)", variable=id_choice_var, 
                   value="Original ID").grid(row=5, column=1, sticky="w")
    
    annotations_var = tk.BooleanVar()
    long_temp_var = tk.BooleanVar()
    txt_var = tk.BooleanVar()

    tk.Checkbutton(window, text="To check if annotation files should be included", variable=annotations_var, onvalue=True,offvalue=False).grid(row=6, column=0, columnspan=2, sticky="w", padx=10, pady=5)
    tk.Checkbutton(window, text="To check if longitudinal temporal information should be maintained", variable=long_temp_var, onvalue=True,offvalue=False).grid(row=7, column=0, columnspan=2, sticky="w", padx=10, pady=5)
    tk.Checkbutton(window, text="To check if .txt files listing DICOM tags of deidentified DICOM files are desired", variable=txt_var, onvalue=True,offvalue=False).grid(row=8, column=0, columnspan=2, sticky="w", padx=10, pady=5)

    # Adding the warning label
    warning_text = ("Warning: Whole slide images are large files. Ensure your disk has enough space: at least as much as the original files.")
    tk.Label(window, text=warning_text, wraplength=400).grid(row=9, column=0, columnspan=3, padx=10, pady=10)

    tk.Button(window, text="Deidentify", command=run_deidentification).grid(row=10, column=0, columnspan=3, pady=20)

    window.mainloop()

if __name__ == '__main__':
    main()

#Bertrand Chauveau
#February 2026
#University of Bordeaux

