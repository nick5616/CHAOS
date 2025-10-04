import cv2
import numpy as np
import yaml
import argparse
# Import the ROI scaling function and icon detection from analyzers
from chaos_lib.analyzers import scale_roi_for_resolution, _detect_headshot_icon, _detect_smoke_icon

def tune_kill_detection(video_path: str, start_time: int, config_path: str = 'config.yaml'):
    print("--- CHAOS Kill Detection Tuner ---")
    print("Controls:")
    print("  'd' / Right Arrow -> Next Frame (+1)")
    print("  's' / Down Arrow  -> Next Second (+_fps)")
    print("  'a' / Left Arrow  -> Previous Frame (-1)")
    print("  'w' / Up Arrow    -> Previous Second (-_fps)")
    print("  'j'               -> Jump to a specific second")
    print("  'q'               -> Quit")
    print("\nWatch the 'Red Mask' and 'Contours' windows while you edit 'config.yaml'.")
    print("Your goal is to make the killfeed border bright white in the mask,")
    print("and for the rectangle around it to be GREEN in the contours view.")
    print("------------------------------------")

    # Load the initial config
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video file at {video_path}")
        return
        
    # Get video resolution for ROI scaling
    video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Video resolution: {video_width}x{video_height}")
        
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps == 0:
        print("Warning: Could not determine video FPS. Defaulting to 30.")
        fps = 30

    frame_idx = int(start_time * fps)

    while 0 <= frame_idx < total_frames:
        # Set the frame position
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            print("End of video.")
            break

        # --- Reload config on every frame to get live updates ---
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
        except Exception as e:
            print(f"Error reading config.yaml: {e}")
            pass # Keep using old config if file is malformed

        # Get parameters from config
        hsv_lower1 = np.array(config['red_hsv_lower1'])
        hsv_upper1 = np.array(config['red_hsv_upper1'])
        hsv_lower2 = np.array(config['red_hsv_lower2'])
        hsv_upper2 = np.array(config['red_hsv_upper2'])
        min_h = config['killfeed_rect_min_height']
        max_h = config['killfeed_rect_max_height']
        min_aspect_ratio = config['killfeed_rect_min_aspect_ratio']
        roi_coords = config['killfeed_roi']
        x1, y1, x2, y2 = scale_roi_for_resolution(roi_coords, video_width, video_height)
        
        killfeed_crop = frame[y1:y2, x1:x2]
        hsv = cv2.cvtColor(killfeed_crop, cv2.COLOR_BGR2HSV)
        mask1 = cv2.inRange(hsv, hsv_lower1, hsv_upper1)
        mask2 = cv2.inRange(hsv, hsv_lower2, hsv_upper2)
        red_mask = cv2.bitwise_or(mask1, mask2)
        
        contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        contours_visualization = killfeed_crop.copy()
        
        current_time_sec = frame_idx / fps
        print(f"\n--- Frame {frame_idx} (Time: {current_time_sec:.2f}s) ---")
        if not contours:
            print("No red contours detected.")
            
        for i, cnt in enumerate(contours):
            x, y, w, h = cv2.boundingRect(cnt)
            aspect_ratio = w / h if h > 0 else 0
            
            height_ok = min_h <= h <= max_h
            aspect_ok = aspect_ratio >= min_aspect_ratio
            is_valid_kill = height_ok and aspect_ok
            
            # Check for special kill types
            kill_region = killfeed_crop[y:y+h, x:x+w]
            is_headshot = _detect_headshot_icon(kill_region)
            through_smoke = _detect_smoke_icon(kill_region)
            
            print(f"Contour #{i}: Pos=({x},{y}) Size=({w}x{h}) Height OK? {height_ok} | Aspect Ratio={aspect_ratio:.2f} OK? {aspect_ok}")
            if is_headshot:
                print(f"  -> HEADSHOT DETECTED!")
            if through_smoke:
                print(f"  -> SMOKE KILL DETECTED!")

            # Color coding: Green=valid, Red=invalid, Blue=headshot, Orange=smoke
            if is_headshot:
                color = (255, 0, 0)  # Blue for headshot
            elif through_smoke:
                color = (0, 165, 255)  # Orange for smoke
            elif is_valid_kill:
                color = (0, 255, 0)  # Green for valid
            else:
                color = (0, 0, 255)  # Red for invalid
                
            # Draw main kill rectangle
            cv2.rectangle(contours_visualization, (x, y), (x + w, y + h), color, 2)
            cv2.putText(contours_visualization, f"H:{h}", (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
            cv2.putText(contours_visualization, f"AR:{aspect_ratio:.1f}", (x, y + h + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
            
            # Draw individual icon detection rectangles
            if is_headshot or through_smoke:
                # Find and highlight the specific icon that was detected
                gray = cv2.cvtColor(kill_region, cv2.COLOR_BGR2GRAY)
                if is_headshot:
                    # Look for headshot icon specifically
                    white_mask = cv2.inRange(gray, 220, 255)
                    icon_contours, _ = cv2.findContours(white_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    for icon_cnt in icon_contours:
                        icon_area = cv2.contourArea(icon_cnt)
                        if 30 < icon_area < 300:
                            icon_x, icon_y, icon_w, icon_h = cv2.boundingRect(icon_cnt)
                            # Draw blue rectangle around the detected headshot icon
                            cv2.rectangle(contours_visualization, 
                                        (x + icon_x, y + icon_y), 
                                        (x + icon_x + icon_w, y + icon_y + icon_h), 
                                        (255, 0, 0), 3)  # Bright blue for headshot icon
                            cv2.putText(contours_visualization, "HS", 
                                      (x + icon_x, y + icon_y - 5), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 0, 0), 1)
                
                if through_smoke:
                    # Look for smoke icon specifically - use same logic as detection
                    smoke_mask = cv2.inRange(gray, 120, 200)  # Medium gray, not bright white
                    icon_contours, _ = cv2.findContours(smoke_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    for icon_cnt in icon_contours:
                        icon_area = cv2.contourArea(icon_cnt)
                        if 40 < icon_area < 150:  # Same size range as detection
                            icon_x, icon_y, icon_w, icon_h = cv2.boundingRect(icon_cnt)
                            icon_aspect = icon_w / icon_h if icon_h > 0 else 0
                            if 0.7 < icon_aspect < 1.4:  # Same aspect ratio as detection
                                # Draw orange rectangle around the detected smoke icon
                                cv2.rectangle(contours_visualization, 
                                            (x + icon_x, y + icon_y), 
                                            (x + icon_x + icon_w, y + icon_y + icon_h), 
                                            (0, 165, 255), 3)  # Orange for smoke icon
                                cv2.putText(contours_visualization, "SM", 
                                          (x + icon_x, y + icon_y - 5), 
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 165, 255), 1)
            
            # Add special labels
            if is_headshot:
                cv2.putText(contours_visualization, "HEADSHOT", (x, y + h + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
            if through_smoke:
                cv2.putText(contours_visualization, "SMOKE", (x, y + h + 45), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        # Display the windows
        cv2.imshow("Original Full Frame (press 'j' to jump)", cv2.resize(frame, (960, 540)))
        cv2.imshow("Killfeed ROI", killfeed_crop)
        cv2.imshow("Red Mask", red_mask)
        cv2.imshow("Contours (Green=Valid, Red=Invalid, Blue=Headshot, Orange=Smoke)", contours_visualization)

        # --- Keyboard Controls ---
        key = cv2.waitKey(0) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('d') or key == 83: # 'd' or right arrow
            frame_idx += 1
        elif key == ord('a') or key == 81: # 'a' or left arrow
            frame_idx = max(0, frame_idx - 1)
        elif key == ord('s') or key == 84: # 's' or down arrow
             frame_idx += int(fps)
        elif key == ord('w') or key == 82: # 'w' or up arrow
             frame_idx = max(0, frame_idx - int(fps))
        elif key == ord('j'):
            try:
                # Close windows temporarily to allow input
                cv2.destroyAllWindows()
                jump_sec = float(input("Enter time in seconds to jump to: "))
                frame_idx = int(jump_sec * fps)
            except ValueError:
                print("Invalid input. Please enter a number.")
                # Re-show the windows if input fails
                continue

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visual tuner for CHAOS kill detection.")
    parser.add_argument('--video', required=True, help="Path to the video file to analyze.")
    parser.add_argument('--start-time', type=int, default=0, help="Optional time in seconds to start the analysis from.")
    args = parser.parse_args()
    tune_kill_detection(args.video, args.start_time)