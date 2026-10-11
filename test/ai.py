#!/bin/bash

from PIL import Image
from pathlib import Path
import numpy as np
from tqdm import tqdm

# Configuration
IMAGE_SIZE = (832, 1024)  # Pillow uses (width, height)
SUPPORTED_FORMATS = {".png", ".jpg", ".jpeg"}
def model_path(filename: str | Path) -> Path:
    """Normalize a model filename to use the .npz extension."""
    return Path(filename).with_suffix(".npz")

# Model Workflows
def create_model(input_count: int, neuron_count: int, filename: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """Create and save a model with configurable inputs and neurons."""
    if input_count <= 0 or neuron_count <= 0:
        raise ValueError("Input and neuron counts must be positive.")
    W = np.random.randn(neuron_count, input_count) * 0.01
    b = np.zeros(neuron_count)
    path = model_path(filename)
    np.savez(path, weights=W, biases=b)
    print(f"Model parameters saved to {path}")
    print("Weight matrix shape:", W.shape)
    print("Bias vector shape:", b.shape)
    return W, b

def load_model(filename: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """Load model weights and biases into memory."""
    path = model_path(filename)
    with np.load(path) as data:
        W = data["weights"]
        b = data["biases"]
    return W, b

# Helpers
def conv(img: str | Path) -> None:
    """Convert an image to RGB and save it as PNG."""
    img = Path(img)
    output_path = img.with_suffix(".png")
    with Image.open(img) as image:
        image.convert("RGB").save(output_path, "PNG")
    print(f"Converted image saved to {output_path}")

def proc_img(filename: str | Path) -> np.ndarray:
    """Process an image into a normalized, flattened RGB vector."""
    path = Path(filename)
    with Image.open(path) as image:
        image = image.convert("RGB")
        image = image.resize(IMAGE_SIZE)
        pixels = np.array(image, dtype=np.float32)
    vector = pixels.flatten() / 255.0
    return vector

# Debug Prints
def pimg(img: str | Path) -> None:
    """Print an image's details and first ten pixel values."""
    path = Path(img)
    with Image.open(path) as image:
        print("Image:", path)
        print("Size:", image.size)
        print("Mode:", image.mode)
        print("First ten pixel values:", list(image.getdata())[:10])

def pimg_diff(img: str | Path) -> None:
    """Print image details and raw RGB values before and after conversion."""
    path = Path(img)
    with Image.open(path) as image:
        print("Original image:")
        print("Size:", image.size)
        print("Mode:", image.mode)
        print("First ten pixel values:", list(image.getdata())[:10])
        rgb_image = image.convert("RGB")
        print("\nAfter RGB conversion:")
        print("Size:", rgb_image.size)
        print("Mode:", rgb_image.mode)
        print("First ten RGB values:", list(rgb_image.getdata())[:10])

# Activation Function
def sigmoid(z: np.ndarray) -> np.ndarray:
    """Map raw neuron outputs to values between zero and one."""
    z = np.clip(z, -60.0, 60.0)
    return 1.0 / (1.0 + np.exp(-z))

# Inference
def run(image: str | Path, model: str | Path) -> np.ndarray:
    """Run one forward pass and return raw neuron output."""
    W, B = load_model(model)
    inputs = proc_img(image)
    if inputs.size != W.shape[1]:
        raise ValueError(
            f"Image produces {inputs.size} inputs, "
            f"but model expects {W.shape[1]}."
        )
    return W @ inputs + B

# Training
def train(model: str | Path, yes_dir: str | Path, no_dir: str | Path, epochs: int, learning_rate: float = 0.001) -> tuple[np.ndarray, np.ndarray]:
    """Train a single-output binary classifier with gradient descent."""
    path = model_path(model)
    yes_dir = Path(yes_dir)
    no_dir = Path(no_dir)
    if epochs <= 0:
        raise ValueError("Epochs must be positive.")
    if learning_rate <= 0:
        raise ValueError("Learning rate must be positive.")
    if not yes_dir.is_dir() or not no_dir.is_dir():
        raise NotADirectoryError(
            "Both yes_dir and no_dir must be existing directories."
        )
    W, B = load_model(path)
    if W.ndim != 2 or W.shape[0] != 1 or B.shape != (1,):
        raise ValueError(
            "This trainer requires one output neuron and one bias."
        )
    expected_inputs = IMAGE_SIZE[0] * IMAGE_SIZE[1] * 3
    if W.shape[1] != expected_inputs:
        raise ValueError(
    f"Model expects {W.shape[1]} inputs, but proc_img "
            f"produces {expected_inputs}. Recreate the model "
            "or use matching image dimensions."
        )
    samples = []
    for directory, target in (
        (yes_dir, 1.0),
        (no_dir, 0.0),
    ):
        for image_path in directory.iterdir():
            if (
                image_path.is_file()
                and image_path.suffix.lower() in SUPPORTED_FORMATS
            ):
                samples.append((image_path, target))
    if not samples:
        raise ValueError("No supported images found in the training directories.")

    for epoch in tqdm(range(epochs), desc="Training epochs"):
        np.random.shuffle(samples)
        total_loss = 0.0
        progress = tqdm(
            samples,
            desc=f"Epoch {epoch + 1}/{epochs}",
            leave=False,
        )
        for i, (image_path, target) in enumerate(progress):
            inputs = proc_img(image_path)

            # Forward pass.
            z = W @ inputs + B
            prediction = sigmoid(z)

            # Binary cross-entropy loss.
            p = float(np.clip(prediction[0], 1e-7, 1.0 - 1e-7))

            loss = -(
                target * np.log(p)
                + (1.0 - target) * np.log(1.0 - p)
            )
            total_loss += loss

            # Backpropagation for sigmoid + binary cross-entropy.
            dz = prediction - target
            dW = dz.reshape(-1, 1) @ inputs.reshape(1, -1)
            dB = dz

            # Gradient descent.
            W -= learning_rate * dW
            B -= learning_rate * dB

            progress.set_postfix(
                loss=f"{total_loss / (i + 1):.4f}"
            )
        tqdm.write(
            f"Epoch {epoch + 1}/{epochs} — "
            f"average loss: {total_loss / len(samples):.4f}"
        )
        
    # Use the same parameter keys as create_model() and load_model().
    np.savez(path, weights=W, biases=B)
    print(f"Trained model saved to {path}")
    return W, B
