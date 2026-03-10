def warmup_models(self):
    import numpy as np

    dummy_h = yaml_config['video']['height']
    dummy_w = yaml_config['video']['width']
    dummy_frame = np.zeros((dummy_h, dummy_w, 3), dtype=np.uint8)

    for roi_coords in self.ROIs_FOR_PROCESSING:
        rx1, ry1, rx2, ry2 = roi_coords
        roi_crop = dummy_frame[ry1:ry2, rx1:rx2]

        self.person_model.predict(
            roi_crop,
            imgsz=yaml_config['model']['person_detection']['imgsz'],
            conf=yaml_config['model']['person_detection']['conf'],
            device=0,
            half=False,
            verbose=False
        )

        self.ppe_model.predict(
            roi_crop,
            imgsz=yaml_config['model']['ppe_detection']['imgsz'],
            conf=yaml_config['model']['ppe_detection']['conf'],
            device=0,
            half=False,
            verbose=False
        )

    torch.cuda.synchronize()
    print("Models warmed up")
