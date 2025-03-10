import os
import re
from lxml import etree
import dateparser
import sys
from tqdm import tqdm

from .baroque_validator import BaroqueValidator
from .utils import sanitize_text

# Note: Some namespaces referenced in the example XML files are not used in the METS file. Unless I'm missing some, these are: fits, fn, rights, marc21 and  tcf.
namespaces = {
    'mets': 'http://www.loc.gov/METS/',
    'dc': 'http://purl.org/dc/elements/1.1',
    'aes': 'http://www.aes.org/audioObject',
    'ph': 'http://www.aes.org/processhistory',
    'mods': 'http://www.loc.gov/mods/v3',
    'xlink': 'http://www.w3.org/1999/xlink'
}


class MetsValidator(BaroqueValidator):
    def __init__(self, project):
        validation = "mets"
        validator = self.validate_mets
        super().__init__(validation, validator, project)

    def check_tag_text(self, tag, argument, value=None):
        """
        Helper function to check an element's value against an expected value"""
        tag_text = sanitize_text(tag.text)
        value = sanitize_text(value)
        if argument == "Is":
            if tag_text != value:
                self.error(
                    self.path_to_mets,
                    self.item_id,
                    tag_text + ' text does not equal ' + value + ' value in ' + tag.tag
                )

    def check_tag_attrib(self, tag, attribute, argument, value=None):
        """
        Helper function that checks that an attribute exists and/or that it's value matches an expected value"""
        if argument == "Exists":  # Does Not Exist, Is, Is Not, Contains, Does Not Contain, Is Greater Than, Is At Least, Is Less Than
            self.check_tag_attrib_exists(tag, attribute)
        elif argument == "Is":
            # checking if the attribute equals a certain value requires first checking that the attribute exists
            exists = self.check_tag_attrib_exists(tag, attribute)
            if exists:
                self.check_tag_attrib_equals(tag, attribute, value)
        else:
            print("unsupported argument " + argument + " for check_tag_attrib")
            sys.exit()

    def check_tag_attrib_exists(self, tag, attribute):
        """
        Helper function to check if a tag attribute exists"""
        exists = True
        if attribute not in tag.attrib:
            self.error(
                self.path_to_mets,
                self.item_id,
                attribute + ' attribute does not exists in ' + tag.tag
            )
            exists = False
        return exists

    def check_tag_attrib_equals(self, tag, attribute, value):
        """
        Helper function to compare a tag's attribute value to an expected value"""
        if tag.attrib.get(attribute) != value:
            self.error(
                self.path_to_mets,
                self.item_id,
                tag.attrib.get(attribute) + ' in ' + attribute + ' attribute does not equal ' + value + ' value in ' + tag.tag
            )

    def check_element_exists(self, element_path):
        """
        Helper function to check if a specific element exists"""
        elements = self.tree.xpath(element_path, namespaces=namespaces)
        element = None
        exists = True
        if len(elements) == 0:
            self.error(
                self.path_to_mets,
                self.item_id,
                'mets xml has no element {}'.format(element_path)
            )
            exists = False
        elif len(elements) > 1:
            self.error(
                self.path_to_mets,
                self.item_id,
                "mets xml has multiple {} elements".format(element_path)
            )
            exists = False
        else:
            element = elements[0]

        return element, exists

    def check_subelements_exist(self, element, subelement_path, expected=False):
        """
        Helper function that checks if one or more of a given subelement exist
        Optionally takes an expected parameter to check for an exact number of subelements
        Returns a list of all matching subelements"""
        subelements = element.findall(subelement_path, namespaces=namespaces)
        exist = True
        if expected and (len(subelements) != expected):
            self.error(
                self.path_to_mets,
                self.item_id,
                "{} {} subelements found in {}, expected {}".format(len(subelements), subelement_path, element.tag, expected)
            )
            exist = False
        elif len(subelements) == 0:
            self.error(
                self.path_to_mets,
                self.item_id,
                "No {} subelements found in {}".format(subelement_path, element.tag)
            )
            exist = False

        return subelements, exist

    def check_dates(self, metadata_date, mets_date):
        """
        Helper function that compares dates from a metadata spreadsheet and METS XML"""
        metadata_date = sanitize_text(metadata_date)
        if metadata_date == "Undated" and mets_date == "undated":
            pass
        # Trying to get around character encoding issues at the end of dates discovered during testing
        if dateparser.parse(metadata_date) != dateparser.parse(mets_date) and dateparser.parse(metadata_date[:-1]) != dateparser.parse(mets_date):
            self.error(
                    self.path_to_mets,
                    self.item_id,
                    metadata_date + ' date in metadata export does not equal ' + mets_date + ' date in mets'
            )

    def check_subelement_exists(self, element, subelement_path):
        """
        Helper function to check if a subelement exists
        Returns a single subelement"""
        subelement = element.find(subelement_path, namespaces=namespaces)
        exists = True
        if subelement is None:
            self.error(
                self.path_to_mets,
                self.item_id,
                "subelement {} not found in {}".format(subelement_path, element.tag)
            )
            exists = False

        return subelement, exists

    def validate_root_element(self):
        """
        Validates root mets element"""
        mets_element, exists = self.check_element_exists("/mets:mets")

        if exists:
            mets_element_nsmap = mets_element.nsmap
            for ns, namespace in namespaces.items():
                if not mets_element_nsmap.get(ns) == namespace:
                    self.error(
                        self.path_to_mets,
                        self.item_id,
                        "mets xml is missing the following namespace: {}:{}".format(ns, namespace)
                    )

            self.check_tag_attrib(mets_element, "OBJID", "Is", self.item_id)
            self.check_tag_attrib(mets_element, "TYPE", "Is", "AUDIO RECORDING") # Note: this assumes BAroQUe will only be used for audio QC

    def validate_mets_header(self):
        """
        Validates metsHdr section

        <mets:metsHdr CREATEDATE="2019-08-05T11:47:37.538-04:00">
            <mets:agent ROLE="OTHER">
                <mets:name>The MediaPreserve</mets:name>
            </mets:agent>
            <mets:agent ROLE="PRESERVATION" TYPE="ORGANIZATION">
                <mets:name>University of Michigan, Bentley Historical Library</mets:name>
            </mets:agent>
            <mets:agent ROLE="DISSEMINATOR" TYPE="ORGANIZATION">
                <mets:name>University of Michigan, Bentley Historical Library</mets:name>
            </mets:agent>
        </mets:metsHdr>"""

        mets_header, exists = self.check_element_exists("/mets:mets/mets:metsHdr")

        if exists:
            # Check that metsHdr attribute CREATE DATE exists
            self.check_tag_attrib(mets_header, "CREATEDATE", "Exists")

            # Check that there are three agent tags
            agents, exist = self.check_subelements_exist(mets_header, "mets:agent", expected=3)
            if exist:
                # Check the MediaPreserve agent
                mediapreserve_agent = agents[0]
                self.check_tag_attrib(mediapreserve_agent, "ROLE", "Is","OTHER")

                mediapreserve_name, exists = self.check_subelement_exists(mediapreserve_agent, "mets:name")
                if exists:
                    self.check_tag_text(mediapreserve_name, "Is", "The MediaPreserve")

                # Check the PRESERVATION Bentley agent
                bhl_preservation_agent = agents[1]
                self.check_tag_attrib(bhl_preservation_agent, "ROLE", "Is", "PRESERVATION")
                self.check_tag_attrib(bhl_preservation_agent, "TYPE", "Is", "ORGANIZATION")

                bhl_preservation_name, exists = self.check_subelement_exists(bhl_preservation_agent, "mets:name")
                if exists:
                    self.check_tag_text(bhl_preservation_name, "Is", "University of Michigan, Bentley Historical Library")

                # Check the DISSEMINATOR Bentley agent
                bhl_disseminator_agent = agents[2]
                self.check_tag_attrib(bhl_disseminator_agent, "ROLE", "Is", "DISSEMINATOR")
                self.check_tag_attrib(bhl_disseminator_agent, "TYPE", "Is", "ORGANIZATION")

                bhl_disseminator_name, exists = self.check_subelement_exists(bhl_disseminator_agent, "mets:name")
                if exists:
                    self.check_tag_text(bhl_disseminator_name, "Is", "University of Michigan, Bentley Historical Library")

    def validate_descriptive_metadata(self):
        """
        Validates dmdSec section"""

        descriptive_metadata, exists = self.check_element_exists("/mets:mets/mets:dmdSec")

        if exists:
            if self.item_metadata:
                mdWrap, exists = self.check_subelement_exists(descriptive_metadata, "mets:mdWrap")
                if exists:
                    self.check_tag_attrib(mdWrap, "MDTYPE", "Is", "DC")
                    self.check_tag_attrib(mdWrap, "LABEL", "Is", "Dublin Core Metadata")
                    xmlData, exists = self.check_subelement_exists(mdWrap, "mets:xmlData")
                    if exists:

                        if self.item_metadata.get("item_title"):
                            dc_title, exists = self.check_subelement_exists(xmlData, "dc:title")
                            if exists:
                                self.check_tag_text(dc_title, "Is", self.item_metadata["item_title"])
                        else:
                            self.warn(
                                self.path_to_mets,
                                self.item_id,
                                "item title not found in metadata export spreadsheet to validate against mets xml"
                            )

                        if self.item_metadata.get("collection_title"):
                            dc_relation, exists = self.check_subelement_exists(xmlData, "dc:relation")
                            if exists:
                                self.check_tag_text(dc_relation, "Is", self.item_metadata["collection_title"])
                        else:
                            self.warn(
                                self.path_to_mets,
                                self.item_id,
                                "collection title not found in metadata export spreadsheet to validate against mets xml"
                            )

                        dc_identifier, exists = self.check_subelement_exists(xmlData, "dc:identifier")
                        if exists:
                            self.check_tag_text(dc_identifier, "Is", self.item_id)

                        if self.item_metadata.get("item_date"):
                            dc_date, exists = self.check_subelement_exists(xmlData, "dc:date")
                            if exists:
                                self.check_dates(self.item_metadata["item_date"], dc_date.text)
                        else:
                            self.warn(
                                self.path_to_mets,
                                self.item_id,
                                "item date not found in metadata export spreadsheet to validate against mets xml"
                            )

                        dc_format, exists = self.check_subelement_exists(xmlData, "dc:format")

                        dc_format_extent, exists = self.check_subelements_exist(xmlData, "dc:format.extent")
            else:
                self.warn(
                    self.path_to_mets,
                    self.item_id,
                    "item has no associated metadata in the metadata export spreadsheet to validate against mets xml"
                )

    def validate_administrative_metadata(self):
        """
        Validates amdSec section"""

        administrative_metadata, exists = self.check_element_exists("/mets:mets/mets:amdSec")

        if exists:
            audio_files = self.item_files["wav"] + self.item_files["mp3"]
            expected_files = audio_files + self.item_files["txt"]
            techMDs, exist = self.check_subelements_exist(administrative_metadata, "mets:techMD", expected=len(expected_files))
            if exist:
                found_files = []
                for techMD in techMDs:
                    if techMD.find("mets:mdRef", namespaces=namespaces) is None:
                        primary_identifier_element, exists = self.check_subelement_exists(techMD, "./mets:mdWrap/mets:xmlData/aes:audioObject/aes:primaryIdentifier")
                        if exists:
                            found_files.append(primary_identifier_element.text)                    
                if sorted(found_files) != sorted(audio_files):
                    self.error(
                        self.path_to_mets,
                        self.item_id,
                        "audio filenames found in amdSec/techMDs do not match files found in directory"
                    )

            sourceMD, _ = self.check_subelement_exists(administrative_metadata, "mets:sourceMD")
            digiprovMD, _ = self.check_subelement_exists(administrative_metadata, "mets:digiprovMD")

    def validate_file_section(self):
        """
        Validates fileSec section"""

        file_section, exists = self.check_element_exists("/mets:mets/mets:fileSec")
        if exists:
            file_groups, exist = self.check_subelements_exist(file_section, "mets:fileGrp", expected=2)
            if exist:
                expected_ids = ["audio-files", "media_images"]
                found_ids = []
                for file_group in file_groups:
                    file_group_id = file_group.attrib.get("ID")
                    found_ids.append(file_group_id)
                    if file_group_id == "audio-files":
                        sub_file_groups, _ = self.check_subelements_exist(file_group, "mets:fileGrp", expected=3)
                if sorted(found_ids) != expected_ids:
                    self.error(
                        self.path_to_mets,
                        self.item_id,
                        "mets xml fileGrp IDs {} do not match expected {}".format(found_ids, expected_ids)
                    )

    def validate_structural_map_section(self):
        """
        Validates structMap section"""

        structural_map_section, exists = self.check_element_exists("/mets:mets/mets:structMap")
        if exists:
            div_one, exists = self.check_subelement_exists(structural_map_section, "mets:div")
            if exists:
                sub_divs, exist = self.check_subelements_exist(div_one, "mets:div")
                if exist:
                    expected_files = self.item_files["wav"] + self.item_files["mp3"]
                    file_pointers = []
                    for sub_div in sub_divs:
                        fptrs = sub_div.findall("mets:fptr", namespaces=namespaces)
                        for fptr in fptrs:
                            file_id = fptr.attrib.get("FILEID").replace("mdp.", "").strip()
                            file_pointers.append(file_id)
                    if sorted(file_pointers) != sorted(expected_files):
                        self.error(
                            self.path_to_mets,
                            self.item_id,
                            "mets structMap fileptr IDs {} do not match expected {}".format(file_pointers, expected_files)
                        )

    def parse_item_mets(self, item):
        """
        Parses item METS"""

        path_to_item = item['path']
        mets = item['files']['xml'][0]

        self.item_id = item['id']
        self.item_files = item["files"]
        self.item_metadata = self.project.metadata["item_metadata"].get(self.item_id)
        self.path_to_mets = os.path.join(path_to_item, mets)
        try:
            self.tree = etree.parse(self.path_to_mets)
            return True
        except:
            self.error(
                self.path_to_mets,
                self.item_id,
                "mets xml is not valid"
            )
            return False

    def validate_mets(self):
        """
        Validates METS"""

        for item in tqdm(self.project.items, desc="METS Validation"):

            # Assuming for now that validating directory and file structure would have picked this up
            if not item['files']['xml']:
                continue
            else:
                if self.parse_item_mets(item):
                    self.validate_root_element()
                    self.validate_mets_header()
                    self.validate_descriptive_metadata()
                    self.validate_administrative_metadata()
                    self.validate_file_section()
                    self.validate_structural_map_section()
