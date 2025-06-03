import unittest
import uuid
from unittest.mock import patch, MagicMock
import pytest
from typing import List, Dict, Any, Optional

# Assuming ContentBlock and FastContentBlockProcessorTool are accessible for import
# Adjust the import path based on your project structure
from aiservice.app.tools.insight_generation_tools import FastContentBlockProcessorTool
from aiservice.app.models.orchestration_models import ContentBlock

class TestReconstructContentFromSummary(unittest.TestCase):

    def setUp(self):
        # Initialize the tool. The user_id can be a test default.
        self.tool = FastContentBlockProcessorTool(user_id="test_user_123")

    def _run_tool(self, summarized_text, image_metadata_list):
        return self.tool._run(
            operation='reconstruct_content_from_summary',
            summarized_text=summarized_text,
            image_metadata_list=image_metadata_list
        )

    def test_summary_with_empty_image_list(self):
        summary = "This is a summary with no images."
        image_list = []
        result = self._run_tool(summary, image_list)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['type'], 'text')
        self.assertEqual(result[0]['content'], summary)
        self.assertEqual(result[0]['order_index'], 0)
        self.assertIsNotNone(result[0]['block_id'])
        self.assertIsNotNone(result[0]['tmp_id'])
        self.assertEqual(result[0]['user_id'], "test_user_123")

        text_blocks = sum(1 for block in result if block['type'] == 'text')
        image_blocks = sum(1 for block in result if block['type'] == 'image')
        print(f"Test: {self._testMethodName} - Text blocks: {text_blocks}, Image blocks: {image_blocks}")

    def test_summary_with_one_image_referenced(self):
        summary = "Summary part 1. [IMAGE: img1] Summary part 2."
        image_list = [{
            "image_id_ref": "img1", "gcs_url": "gs://bucket/img1.jpg", 
            "alt_text": "Alt text 1", "caption": "Caption 1", 
            "width": 100, "height": 100
        }]
        result = self._run_tool(summary, image_list)
        
        self.assertEqual(len(result), 3)
        # Text 1
        self.assertEqual(result[0]['type'], 'text')
        self.assertEqual(result[0]['content'], "Summary part 1.")
        self.assertEqual(result[0]['order_index'], 0)
        # Image 1
        self.assertEqual(result[1]['type'], 'image')
        self.assertEqual(result[1]['image_id_ref'], "img1")
        self.assertEqual(result[1]['gcs_url'], "gs://bucket/img1.jpg")
        self.assertEqual(result[1]['alt_text'], "Alt text 1")
        self.assertEqual(result[1]['caption'], "Caption 1")
        self.assertEqual(result[1]['width'], 100)
        self.assertEqual(result[1]['height'], 100)
        self.assertEqual(result[1]['order_index'], 1)
        # Text 2
        self.assertEqual(result[2]['type'], 'text')
        self.assertEqual(result[2]['content'], "Summary part 2.")
        self.assertEqual(result[2]['order_index'], 2)

        text_blocks = sum(1 for block in result if block['type'] == 'text')
        image_blocks = sum(1 for block in result if block['type'] == 'image')
        print(f"Test: {self._testMethodName} - Text blocks: {text_blocks}, Image blocks: {image_blocks}")

    def test_summary_with_multiple_images_mixed_reference(self):
        summary = "Text before [IMAGE: img1]. Text between. [IMAGE: gs://bucket/img3.png] Final text."
        image_list = [
            {"image_id_ref": "img1", "gcs_url": "gs://bucket/img1.jpg", "caption": "Caption 1", "width": 10, "height": 10},
            {"image_id_ref": "img2_unreferenced", "gcs_url": "gs://bucket/img2.png", "caption": "Caption 2", "width": 20, "height": 20},
            {"image_id_ref": "img3", "gcs_url": "gs://bucket/img3.png", "caption": "Caption 3", "width": 30, "height": 30}
        ]
        result = self._run_tool(summary, image_list)
        
        self.assertEqual(len(result), 6) # 3 text, 2 referenced images, 1 appended image

        # Expected order: Text, Img1, Text, Img3, Text, Img2_unreferenced
        self.assertEqual(result[0]['type'], 'text') # Text before
        self.assertEqual(result[0]['order_index'], 0)

        self.assertEqual(result[1]['type'], 'image') # img1
        self.assertEqual(result[1]['image_id_ref'], "img1")
        self.assertEqual(result[1]['order_index'], 1)

        self.assertEqual(result[2]['type'], 'text') # Text between
        self.assertEqual(result[2]['order_index'], 2)

        self.assertEqual(result[3]['type'], 'image') # img3 (referenced by GCS URL)
        self.assertEqual(result[3]['image_id_ref'], "img3") # Should still pick up the id_ref from metadata
        self.assertEqual(result[3]['gcs_url'], "gs://bucket/img3.png")
        self.assertEqual(result[3]['order_index'], 3)

        self.assertEqual(result[4]['type'], 'text') # Final text
        self.assertEqual(result[4]['order_index'], 4)
        
        self.assertEqual(result[5]['type'], 'image') # img2_unreferenced (appended)
        self.assertEqual(result[5]['image_id_ref'], "img2_unreferenced")
        self.assertEqual(result[5]['gcs_url'], "gs://bucket/img2.png")
        self.assertEqual(result[5]['caption'], "Caption 2")
        self.assertEqual(result[5]['order_index'], 5)

        text_blocks = sum(1 for block in result if block['type'] == 'text')
        image_blocks = sum(1 for block in result if block['type'] == 'image')
        print(f"Test: {self._testMethodName} - Text blocks: {text_blocks}, Image blocks: {image_blocks}")

    def test_summary_with_unreferenced_image_appended(self):
        summary = "This is a summary."
        image_list = [{
            "image_id_ref": "img_extra", "gcs_url": "gs://bucket/img_extra.jpg",
            "alt_text": "Extra Alt", "caption": "Extra Caption",
            "width": 150, "height": 150
        }]
        result = self._run_tool(summary, image_list)
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['type'], 'text')
        self.assertEqual(result[0]['content'], "This is a summary.")
        self.assertEqual(result[0]['order_index'], 0)
        
        self.assertEqual(result[1]['type'], 'image')
        self.assertEqual(result[1]['image_id_ref'], "img_extra")
        self.assertEqual(result[1]['gcs_url'], "gs://bucket/img_extra.jpg")
        self.assertEqual(result[1]['alt_text'], "Extra Alt")
        self.assertEqual(result[1]['caption'], "Extra Caption")
        self.assertEqual(result[1]['width'], 150)
        self.assertEqual(result[1]['height'], 150)
        self.assertEqual(result[1]['order_index'], 1)

        text_blocks = sum(1 for block in result if block['type'] == 'text')
        image_blocks = sum(1 for block in result if block['type'] == 'image')
        print(f"Test: {self._testMethodName} - Text blocks: {text_blocks}, Image blocks: {image_blocks}")

    def test_summary_no_placeholders_multiple_images_appended(self):
        summary = "A simple summary text."
        image_list = [
            {"image_id_ref": "imgA", "gcs_url": "gs://bucket/imgA.jpg", "caption": "A"},
            {"image_id_ref": "imgB", "gcs_url": "gs://bucket/imgB.jpg", "caption": "B"}
        ]
        result = self._run_tool(summary, image_list)

        self.assertEqual(len(result), 3) # 1 text, 2 images
        self.assertEqual(result[0]['type'], 'text')
        self.assertEqual(result[0]['content'], summary)
        self.assertEqual(result[0]['order_index'], 0)

        self.assertEqual(result[1]['type'], 'image')
        self.assertEqual(result[1]['image_id_ref'], "imgA")
        self.assertEqual(result[1]['order_index'], 1)

        self.assertEqual(result[2]['type'], 'image')
        self.assertEqual(result[2]['image_id_ref'], "imgB")
        self.assertEqual(result[2]['order_index'], 2)

        text_blocks = sum(1 for block in result if block['type'] == 'text')
        image_blocks = sum(1 for block in result if block['type'] == 'image')
        print(f"Test: {self._testMethodName} - Text blocks: {text_blocks}, Image blocks: {image_blocks}")

    def test_image_block_all_fields_populated(self):
        summary = "[IMAGE: test_img_full]"
        image_meta = {
            "image_id_ref": "test_img_full", "gcs_url": "gs://bucket/full.png",
            "alt_text": "Complete Alt", "caption": "Full Caption",
            "width": 200, "height": 250, "some_other_field": "ignored"
        }
        # Ensure all expected fields for an image block are present
        # Add dummy values for other fields ContentBlock might have by default.
        # user_id is set by tool, block_id and tmp_id are generated.
        
        result = self._run_tool(summary, [image_meta])
        self.assertEqual(len(result), 1)
        img_block = result[0]
        
        self.assertEqual(img_block['type'], 'image')
        self.assertEqual(img_block['image_id_ref'], "test_img_full")
        self.assertEqual(img_block['gcs_url'], "gs://bucket/full.png")
        self.assertEqual(img_block['alt_text'], "Complete Alt")
        self.assertEqual(img_block['caption'], "Full Caption")
        self.assertEqual(img_block['width'], 200)
        self.assertEqual(img_block['height'], 250)
        self.assertEqual(img_block['order_index'], 0)
        self.assertIsNotNone(img_block['block_id'])
        self.assertIsNotNone(img_block['tmp_id'])
        self.assertEqual(img_block['user_id'], "test_user_123")
        # Ensure non-ContentBlock fields from metadata are not just passed through
        self.assertNotIn("some_other_field", img_block)

        text_blocks = sum(1 for block in result if block['type'] == 'text')
        image_blocks = sum(1 for block in result if block['type'] == 'image')
        print(f"Test: {self._testMethodName} - Text blocks: {text_blocks}, Image blocks: {image_blocks}")

    def test_image_without_id_ref_in_metadata_handled(self):
        summary = "Text. [IMAGE: gs://bucket/no_id.jpg] More text."
        # Image in list has GCS URL but no image_id_ref
        image_list = [{
            "gcs_url": "gs://bucket/no_id.jpg", "caption": "No ID Image",
            "width": 50, "height": 50 
        }]
        # We also add another image with an ID ref that is unreferenced, to test appending
        image_list.append({
            "image_id_ref": "unreferenced_img", "gcs_url": "gs://bucket/unreferenced.jpg",
            "caption": "Unreferenced", "width": 60, "height": 60
        })
        
        # Mock print to check for the warning
        with patch('builtins.print') as mock_print:
            result = self._run_tool(summary, image_list)
        
        self.assertEqual(len(result), 4) # Text, Image (no_id), Text, Image (unreferenced_img)
        
        self.assertEqual(result[0]['type'], 'text')
        self.assertEqual(result[0]['order_index'], 0)
        
        self.assertEqual(result[1]['type'], 'image')
        self.assertIsNone(result[1]['image_id_ref']) # image_id_ref was None in meta
        self.assertEqual(result[1]['gcs_url'], "gs://bucket/no_id.jpg")
        self.assertEqual(result[1]['caption'], "No ID Image")
        self.assertEqual(result[1]['order_index'], 1)
        
        self.assertEqual(result[2]['type'], 'text')
        self.assertEqual(result[2]['order_index'], 2)

        self.assertEqual(result[3]['type'], 'image') # The unreferenced image
        self.assertEqual(result[3]['image_id_ref'], "unreferenced_img")
        self.assertEqual(result[3]['gcs_url'], "gs://bucket/unreferenced.jpg")
        self.assertEqual(result[3]['order_index'], 3)

        # Check if the warning for the unreferenced_img (which has an id) NOT being added via placeholder was NOT printed
        # (it should be added silently at the end).
        # Check if a warning about the GCS-only image was printed during the append phase (it shouldn't be appended if matched by placeholder,
        # and if not matched and no id_ref, it will print a warning in the append loop).
        # The current code *will* print a warning in the append loop for an image metadata without an 'image_id_ref'
        # if it wasn't already processed by a placeholder.
        # In this case, 'gs://bucket/no_id.jpg' IS processed by placeholder. So it won't reach the append loop's warning.
        # 'unreferenced_img' has an id_ref, so it won't trigger that specific warning either.
        
        # Let's refine the check: ensure no "Skipping its addition" warning for 'unreferenced_img'
        # and that 'gs://bucket/no_id.jpg' was processed.
        
        # This specific warning: "Warning: Image metadata found without an 'image_id_ref'. Skipping its addition"
        # should NOT appear for gs://bucket/no_id.jpg because it's handled by placeholder.
        # It also shouldn't appear for unreferenced_img as it has an ID.
        
        found_skipping_warning = False
        for call_args in mock_print.call_args_list:
            if "Warning: Image metadata found without an 'image_id_ref'. Skipping its addition" in call_args[0][0]:
                found_skipping_warning = True
                break
        self.assertFalse(found_skipping_warning, "Should not print skipping warning for images handled by placeholder or having an ID.")

        text_blocks = sum(1 for block in result if block['type'] == 'text')
        image_blocks = sum(1 for block in result if block['type'] == 'image')
        # We use original print here, as mock_print is out of scope or might interfere with other tests if not reset.
        # For simplicity in this specific request, printing directly. In a real scenario, might pass mock_print or use a logger.
        import builtins
        builtins.print(f"Test: {self._testMethodName} - Text blocks: {text_blocks}, Image blocks: {image_blocks}")

    def test_e2e_like_reconstruction(self):
        summary = (
            "This is the introduction. [IMAGE: id_ref_img1] Some more text here. "
            "Then we reference an image by its GCS URL [IMAGE: gs://bucket/e2e_img2.png]. "
            "Followed by another referenced image [IMAGE: id_ref_img3]. And a final piece of text."
        )
        image_list = [
            {
                "image_id_ref": "id_ref_img1", "gcs_url": "gs://bucket/e2e_img1.jpg",
                "alt_text": "Alt 1", "caption": "Caption E2E 1", "width": 100, "height": 101
            },
            { # Referenced by GCS URL in summary, has an image_id_ref in metadata
                "image_id_ref": "id_ref_for_gcs_img2", "gcs_url": "gs://bucket/e2e_img2.png", 
                "alt_text": "Alt 2", "caption": "Caption E2E 2 GCS ref", "width": 200, "height": 202
            },
            {
                "image_id_ref": "id_ref_img3", "gcs_url": "gs://bucket/e2e_img3.webp",
                "alt_text": "Alt 3", "caption": "Caption E2E 3", "width": 300, "height": 303
            },
            { # Unreferenced, should be appended
                "image_id_ref": "unreferenced_e2e_img4", "gcs_url": "gs://bucket/e2e_img4.gif",
                "alt_text": "Alt 4", "caption": "Caption E2E 4 Unreferenced", "width": 400, "height": 404
            },
            { # Another unreferenced, should be appended after img4
                "image_id_ref": "unreferenced_e2e_img5", "gcs_url": "gs://bucket/e2e_img5.bmp",
                "alt_text": "Alt 5", "caption": "Caption E2E 5 Unreferenced", "width": 500, "height": 505
            }
        ]

        result = self._run_tool(summary, image_list)

        self.assertEqual(len(result), 4 + 3 + 2) # 4 text segments, 3 referenced images, 2 appended images

        # Text 1
        self.assertEqual(result[0]['type'], 'text')
        self.assertEqual(result[0]['content'], "This is the introduction.")
        self.assertEqual(result[0]['order_index'], 0)

        # Image 1 (id_ref_img1)
        self.assertEqual(result[1]['type'], 'image')
        self.assertEqual(result[1]['image_id_ref'], "id_ref_img1")
        self.assertEqual(result[1]['gcs_url'], "gs://bucket/e2e_img1.jpg")
        self.assertEqual(result[1]['caption'], "Caption E2E 1")
        self.assertEqual(result[1]['order_index'], 1)

        # Text 2
        self.assertEqual(result[2]['type'], 'text')
        self.assertEqual(result[2]['content'], "Some more text here. Then we reference an image by its GCS URL")
        self.assertEqual(result[2]['order_index'], 2)

        # Image 2 (gs://bucket/e2e_img2.png)
        self.assertEqual(result[3]['type'], 'image')
        self.assertEqual(result[3]['image_id_ref'], "id_ref_for_gcs_img2") # Found via GCS URL, but full meta used
        self.assertEqual(result[3]['gcs_url'], "gs://bucket/e2e_img2.png")
        self.assertEqual(result[3]['caption'], "Caption E2E 2 GCS ref")
        self.assertEqual(result[3]['order_index'], 3)

        # Text 3
        self.assertEqual(result[4]['type'], 'text')
        self.assertEqual(result[4]['content'], ". Followed by another referenced image")
        self.assertEqual(result[4]['order_index'], 4)

        # Image 3 (id_ref_img3)
        self.assertEqual(result[5]['type'], 'image')
        self.assertEqual(result[5]['image_id_ref'], "id_ref_img3")
        self.assertEqual(result[5]['gcs_url'], "gs://bucket/e2e_img3.webp")
        self.assertEqual(result[5]['order_index'], 5)

        # Text 4
        self.assertEqual(result[6]['type'], 'text')
        self.assertEqual(result[6]['content'], ". And a final piece of text.")
        self.assertEqual(result[6]['order_index'], 6)

        # Appended Image 4 (unreferenced_e2e_img4)
        self.assertEqual(result[7]['type'], 'image')
        self.assertEqual(result[7]['image_id_ref'], "unreferenced_e2e_img4")
        self.assertEqual(result[7]['gcs_url'], "gs://bucket/e2e_img4.gif")
        self.assertEqual(result[7]['order_index'], 7)

        # Appended Image 5 (unreferenced_e2e_img5)
        self.assertEqual(result[8]['type'], 'image')
        self.assertEqual(result[8]['image_id_ref'], "unreferenced_e2e_img5")
        self.assertEqual(result[8]['gcs_url'], "gs://bucket/e2e_img5.bmp")
        self.assertEqual(result[8]['order_index'], 8)
        
        text_blocks = sum(1 for block in result if block['type'] == 'text')
        image_blocks = sum(1 for block in result if block['type'] == 'image')
        import builtins
        builtins.print(f"Test: {self._testMethodName} - Text blocks: {text_blocks}, Image blocks: {image_blocks}")

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False) 