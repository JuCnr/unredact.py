import os
import fitz  # PyMuPDF
import glob

def bypass_xref_reconstruction(input_folder, output_folder):
    if not os.path.exists(output_folder): os.makedirs(output_folder)
    files = glob.glob(os.path.join(input_folder, "*.pdf"))

    for file_path in files:
        fname = os.path.basename(file_path)
        print(f"\n[CLEANING] {fname}")
        try:
            doc = fitz.open(file_path)
            new_doc = fitz.open() 
            
            for page in doc:
                # Create a fresh page (drawings/vector paths are not copied)
                new_page = new_doc.new_page(width=page.rect.width, height=page.rect.height)
                
                # --- STEP 1: RESTORE IMAGES (MANUAL PIXEL CHECK) ---
                page_images = page.get_images(full=True)
                
                for img in page_images:
                    xref = img[0]
                    try:
                        img_rects = page.get_image_rects(xref)
                        if not img_rects:
                            continue
                            
                        target_rect = img_rects[0]
                        
                        if target_rect.height > 10:
                            pix = fitz.Pixmap(doc, xref)
                            
                            # Ensure we are working with an RGB or Gray image to check brightness
                            if pix.colorspace.n > 3: # CMYK
                                check_pix = fitz.Pixmap(fitz.csRGB, pix)
                            else:
                                check_pix = pix

                            # Calculate average brightness manually from the pixel samples
                            # sum(samples) / total pixels / number of components
                            pixels = check_pix.samples
                            avg_brightness = sum(pixels) / len(pixels)
                            
                            # TARGET BLACK BOXES:
                            # 0 is pure black, 255 is pure white. 
                            # Redaction boxes are typically < 10.
                            is_black_redaction = avg_brightness < 15
                            
                            if not is_black_redaction:
                                new_page.insert_image(target_rect, pixmap=pix)
                            else:
                                print(f"  [REMOVED] Black redaction box at {target_rect} (Brightness: {avg_brightness:.2f})")
                                
                            pix = None 
                            if check_pix != pix: check_pix = None
                            
                    except Exception as e:
                        print(f"  [DEBUG] Skipping image xref {xref}: {e}")

                # --- STEP 2: RECOVER DIGITAL TEXT ---
                text_dict = page.get_text("dict")
                for block in text_dict["blocks"]:
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            if span["text"].strip():
                                new_page.insert_text(
                                    span["origin"], 
                                    span["text"], 
                                    fontsize=span["size"], 
                                    color=(1, 0, 0), # Red
                                    overlay=True
                                )

            out_path = os.path.join(output_folder, f"CLEANED_{fname}")
            new_doc.save(out_path, garbage=4, deflate=True)
            doc.close()
            new_doc.close()
            print(f"✅ Success: Processed {fname}")
            
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    in_dir = input("Input: ").strip().replace('"', '')
    out_dir = input("Output: ").strip().replace('"', '')
    bypass_xref_reconstruction(in_dir, out_dir)