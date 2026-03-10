def load_models_half(self):
    self.person_model = YOLO(resource_path(yaml_config['paths']['person_model'])).to("cuda")
    self.ppe_model = YOLO(resource_path(yaml_config['paths']['ppe_model'])).to("cuda")

    dummy = torch.zeros(1, 3, 640, 640).cuda().half()
    self.person_model.predict(
        source=dummy,
        imgsz=640,
        conf=0.3,
        device=0,
        half=True,
        verbose=False
    )
    self.ppe_model.predict(
        source=dummy,
        imgsz=640,
        conf=0.3,
        device=0,
        half=True,
        verbose=False
    )


def predict_person_half(self, roi_img, roi_index):
    return self.person_model.predict(
        roi_img,
        imgsz=yaml_config['model']['person_detection']['imgsz'],
        conf=yaml_config['model']['person_detection']['conf'],
        device=0,
        half=True,
        verbose=False
    )[0]


def predict_ppe_half(self, roi_img):
    return self.ppe_model.predict(
        roi_img,
        imgsz=yaml_config['model']['ppe_detection']['imgsz'],
        conf=yaml_config['model']['ppe_detection']['conf'],
        device=0,
        half=True,
        verbose=False
    )[0]


def predict_vehicle_half(self, roi_img):
    return self.person_model.predict(
        roi_img,
        imgsz=yaml_config['model']['vehicle_detection']['imgsz'],
        conf=yaml_config['model']['vehicle_detection']['conf'],
        device=0,
        half=True,
        verbose=False
    )[0]
