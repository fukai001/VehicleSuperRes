import argparse
import cv2
from glob import glob
import numpy as np
import os
import os.path as path
from time import time

import torch
import torch.nn as nn
from torchvision import datasets, transforms, utils


# CLI parser
parser = argparse.ArgumentParser(description="Vehicle Super Resolution Converter")
subparsers = parser.add_subparsers(help="commands")

image_parser = subparsers.add_parser("image", help="Convert Image")
image_parser.add_argument("-i", type=str, default="./images", metavar="INPUT", help="Input image batch directory (default: ./images)")
image_parser.add_argument("-o", type=str, default="./output", metavar="OUTPUT", help="Output image directory (default: ./output)")
image_parser.add_argument("-w", type=str, default="weights.pth", metavar="WEIGHTS", help="Path to weights file (default: weights-beta.pth)")
image_parser.add_argument("--ext", type=str, default="(keep)", metavar="ext", help="File extension for output (default: <uses the same extension as input>)")
image_parser.add_argument("-fps", type=float, default=30.0, metavar="FPS", help="Frame per second for video output (default: 30 FPS)")
image_parser.add_argument("--noise-level", type=int, default=0, metavar="NOISE_LEVEL")
image_parser.add_argument("-v", "--verbose", action="store_true")
image_parser.add_argument("--no-upscale", action="store_true")
image_parser.set_defaults(which="image")

video_parser = subparsers.add_parser("video", help="Convert Video")
video_parser.add_argument("-i", type=str, default="./videos/input.avi", metavar="INPUT", help="Input video (default: ./videos/input.avi)")
video_parser.add_argument("-o", type=str, default="./frames", metavar="OUTPUT", help="Output image directory (default: ./frames)")
video_parser.add_argument("-w", type=str, default="weights.pth", metavar="WEIGHTS", help="Path to weights file (default: weights-beta.pth)")
video_parser.add_argument("--ext", type=str, default="jpg", metavar="ext", help="File extension for output (default: <uses the same extension as input>)")
video_parser.add_argument("-fps", type=float, default=None, metavar="FPS", help="Frame per second for video output (default: <uses the same as input>)")
video_parser.add_argument("--noise-level", type=int, default=0, metavar="NOISE_LEVEL")
video_parser.add_argument("--no-upscale", action="store_true")
video_parser.add_argument("-v", "--verbose", action="store_true")
video_parser.set_defaults(which="video")


# Extensions
image_ext = ["jpg", "png", "bmp"]
video_ext = ["avi"]


# Model Setup
torch.set_default_tensor_type('torch.cuda.FloatTensor')
device = torch.device("cuda")

upscale_model = nn.Sequential(
    nn.Conv2d(3, 16, (3, 3), padding=(1, 1)),
    nn.LeakyReLU(0.1),
    nn.Conv2d(16, 32, (3, 3), padding=(1, 1)),
    nn.LeakyReLU(0.1),
    nn.Conv2d(32, 64, (3, 3), padding=(1, 1)),
    nn.LeakyReLU(0.1),
    nn.Conv2d(64, 128, (3, 3), padding=(1, 1)),
    nn.LeakyReLU(0.1),
    nn.Conv2d(128, 128, (3, 3), padding=(1, 1)),
    nn.LeakyReLU(0.1),
    nn.Conv2d(128, 256, (3, 3), padding=(1, 1)),
    nn.LeakyReLU(0.1),
    nn.ConvTranspose2d(256, 3, (4, 4), (2, 2), (1, 1), (0, 0), bias=False),
    nn.Sigmoid()
).to(device)
upscale_model.eval()

redux_model = nn.Sequential(
    nn.Conv2d(3, 32, (3, 3), padding=(1, 1)),
    nn.LeakyReLU(0.1),
    nn.Conv2d(32, 32, (3, 3), padding=(1, 1)),
    nn.LeakyReLU(0.1),
    nn.Conv2d(32, 64, (3, 3), padding=(1, 1)),
    nn.LeakyReLU(0.1),
    nn.Conv2d(64, 64, (3, 3), padding=(1, 1)),
    nn.LeakyReLU(0.1),
    nn.Conv2d(64, 128, (3, 3), padding=(1, 1)),
    nn.LeakyReLU(0.1),
    nn.Conv2d(128, 128, (3, 3), padding=(1, 1)),
    nn.LeakyReLU(0.1),
    nn.Conv2d(128, 3, (3, 3), padding=(1, 1)),
    nn.Hardtanh(min_val=0)
).to(device)
redux_model.eval()


# Time logging functions
def tic():
    global args, start_time
    if args.verbose: start_time = time()

def toc(log):
    global args, start_time
    if args.verbose: print(log.format(time() - start_time))


# Execution for image command
def image():
    # Load inputs
    tic()
    dataset = datasets.ImageFolder(root=args.i, transform=transforms.ToTensor())
    dataset_loader = torch.utils.data.DataLoader(dataset, batch_size=1, shuffle=False, num_workers=1)
    toc("Prepared dataset in {:6f} seconds.")

    with torch.no_grad():
        if args.type == "video":
            videos = {}

        for idx, x in enumerate(dataset_loader):
            filepath = dataset.samples[idx][0].replace(args.i, args.o)
            if args.ext != "(keep)": filepath = path.splitext(filepath)[0] + "." + args.ext
            directory = path.dirname(filepath)
            if args.type == "image":
                if not os.path.exists(directory): os.makedirs(directory)

            tic()
            input = x[0].cuda()
            output = input if args.no_upscale else upscale_model(input)

            # img1 = output.permute(0, 2, 3, 1).cpu().numpy()
            # img1 = img1.reshape(img1.shape[1:])
            # img1 = img1[:, :, ::-1]
            # cv2.imshow("before", img1)

            output = redux_model(output)

            # img2 = output.permute(0, 2, 3, 1).cpu().numpy()
            # img2 = img2.reshape(img2.shape[1:])
            # img2 = img2[:, :, ::-1]
            # cv2.imshow("after", img2)
            #
            # print(min(img2.reshape(img2.shape[0] * img2.shape[1] * img2.shape[2])))
            # print(max(img2.reshape(img2.shape[0] * img2.shape[1] * img2.shape[2])))
            #
            # cv2.waitKey()
            # cv2.destroyAllWindows()

            if args.verbose: print("{}:\t{} {} --> {} {}".format(idx, dataset.samples[idx][0], tuple(input.shape), filepath, tuple(output.shape)))
            toc("Conversion time: {:06f} seconds.")

            if args.type == "image":
                tic()
                utils.save_image(output, filepath)
                toc("Saved image: {:06f} seconds.")
            elif args.type == "video":
                tic()
                img = output.permute(0, 2, 3, 1).cpu().numpy()
                img = img.reshape(img.shape[1:])
                img = img[:, :, ::-1] * 255

                if directory not in videos:
                    height, width, channels = img.shape
                    videos[directory] = cv2.VideoWriter(directory + "." + args.ext, cv2.VideoWriter_fourcc(*"XVID"), args.fps, (width, height))
                videos[directory].write(np.uint8(img))
                toc("Saved frame: {:06f} seconds.")

        if args.type == "video":
            for video in videos.values():
                video.release()


# Execution for video command
def video():
    # Load inputs
    tic()
    videos = glob(args.i)
    args.i = path.dirname(args.i)
    toc("Found %d video(s) in {:6f} seconds." % len(videos))

    with torch.no_grad():
        for video in videos:
            directory = path.splitext(video.replace(args.i, args.o))[0]
            if args.type == "video":
                filepath = directory + "." + args.ext
                directory = path.dirname(filepath)
            if not os.path.exists(directory): os.makedirs(directory)

            tic()
            cap = cv2.VideoCapture(video)
            toc("Loaded video %s in {:6f} seconds." % video)
            
            time_depth = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            if args.type == "video":
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                if not args.no_upscale:
                    width *= 2
                    height *= 2
                fps = cap.get(cv2.CAP_PROP_FPS) if args.fps is None else args.fps
                video_out = cv2.VideoWriter(filepath, cv2.VideoWriter_fourcc(*"XVID"), fps, (width, height))

            for idx in range(1, time_depth+1):
                if args.type == "image":
                    filepath = path.join(directory, "frame{:07d}.".format(idx) + args.ext)

                tic()
                success, input = cap.read()
                toc("Read frame in {:6f} seconds.")

                if success:
                    tic()
                    input = input[:,:,::-1]
                    input = np.swapaxes(np.swapaxes(np.array(input, dtype=float), 0, 2), 1, 2) / 255.0
                    input = torch.from_numpy(input.reshape((1,) + input.shape)).float().cuda()
                    output = input if args.no_upscale else upscale_model(input)
                    # output = redux_model(output)
                    if args.verbose:
                        if args.type == "image":
                            print("{0}/{1}:\t{2} {3} --> {4} {5}".format(idx, time_depth, video, tuple(input.shape), filepath, tuple(output.shape)))
                        elif args.type == "video":
                            print("{0}/{1}:\t{2} {3} --> {4} [{0}] {5}".format(idx, time_depth, video, tuple(input.shape), filepath, tuple(output.shape)))

                    toc("Conversion time: {:06f} seconds.")

                    if args.type == "image":
                        tic()
                        # cv2.imwrite(filepath, img * 255.0)
                        utils.save_image(output, filepath)
                        toc("Saved image: {:06f} seconds.")
                    elif args.type == "video":
                        tic()
                        img = output.permute(0, 2, 3, 1).cpu().numpy()
                        img = img.reshape(img.shape[1:])
                        img = img[:, :, ::-1] * 255.0
                        # print(img.shape)
                        # cv2.imshow("img", np.uint8(img))
                        # cv2.waitKey()
                        # cv2.destroyAllWindows()
                        video_out.write(np.uint8(img))
                        toc("Saved frame: {:06f} seconds.")

            if args.type == "image":
                pwd = os.getcwd()
                os.chdir(directory)
                os.system("ls -1 frame* > file_list.txt")
                os.chdir(pwd)
            elif args.type == "video":
                video_out.release()



# Main
if __name__ == "__main__":
    global args
    args = parser.parse_args()
    args.ext = args.ext.replace('.', '')
    args.type = "image" if args.ext.lower() in image_ext else "video" if args.ext.lower() in video_ext else None

    if args.noise_level < 0 or args.noise_level > 3:
        print("Bad noise level. Must be an integer between 0 and 3.")
        exit(0)

    # Load weights
    tic()
    upscale_weights = torch.load(args.w)
    upscale_model.load_state_dict(upscale_weights)
    redux_weights = torch.load("noise%d_model.pth" % args.noise_level)
    redux_model.load_state_dict(redux_weights)
    toc("Loaded weights in {:6f} seconds.")

    if args.which is "image":
        if args.ext == "(keep)": args.type = "image"
        image()
    elif args.which is "video":
        video()

