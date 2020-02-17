# Training Process
# Reference: https://www.mitpressjournals.org/doi/10.1162/jocn.1991.3.1.71

# !/usr/bin/python
import os, sys

# original_dir = os.getcwd()
# sys.path.append('/home/pi/.virtualenvs/cv/lib/python3.6/site-packages')  # For Raspberry Pi
import timeit
import cv2
import numpy as np
from PIL import Image


# sys.path.append(original_dir)
def import_images(path, emotion, img_indexes=None, img_amount=None):
    """
    Fetch list of images directory of specific emotion. Specifically work for our file format.
    :param path:        Folder directory where images are stored. Can be list to fetch from multiple folders.
    :param emotion:     String of emotion name. Image name should start with emotion e.g. sad_1010.jpg
    :param img_indexes: List of string of specific image id you want e.g. [1010.jpg]. Use None to fetch all
    :param img_amount:  Amount of image you want to fetch. Use None to fetch all
    :return:            ndarray of size (h*w, img_amount) or (features, num_image)
    """
    if type(path) is not list:
        path = [path]

    image_paths = []
    for p in path:
        if img_indexes is None or len(img_indexes) == 0:
            im_p = [os.path.join(p, f) for f in os.listdir(p) \
                    if f.split("_")[0].endswith(emotion)]  # Get path of file that start with 'emotion'
        else:
            im_p = [os.path.join(p, f) for f in os.listdir(p) \
                    if (f.split("_")[0].endswith(emotion) and f.split("_")[1] in img_indexes)]
        image_paths = image_paths + im_p
    image_paths.sort()

    if img_amount is None:
        img_amount = len(image_paths)
    else:
        assert img_amount <= len(image_paths), "Requested too many images. Amount of image found is {}.".format(
            len(image_paths))

    # Load all image and subtract the value by the average value
    image_vector = np.stack([load_image(image_path) for image_path in image_paths[0:img_amount]])
    image_average = np.tile(np.mean(image_vector, 0), (img_amount, 1)) / img_amount

    image_vector = image_vector - image_average
    # return the images list and average
    return image_vector.T, image_average.T


def load_image(full_path):  # Importing single image
    image = np.array(Image.open(full_path).convert('L'), 'float32')
    [h, w] = np.shape(image)
    image_vec = np.reshape(image, h * w, 'C')
    return image_vec


def create_eigface(images, num_eigen=None, percent_eigen=None):  # Process of creating optimal projection axis
    """
    Function to create eigenface (Using Principal Component Analysis with some extra technique to save computation cost)
    :param images           : ndarray of size (features, num_image)
    :param num_eigen        : int, number of eigenfaces. Cannot be specified with percent_eigen
    :param percent_eigen    : float, number of percentage of eigenvalues for determine number of eigenface

    """
    if num_eigen is not None and percent_eigen is not None:
        raise ValueError("Only one of 'num_eigen' or 'percent_eigen' can be specified")
    if num_eigen is None and percent_eigen is None:
        raise ValueError("Either 'num_eigen' or 'percent_eigen' need to be specified")

    features, num_pic = np.shape(images)
    # Create pseudo covariance matrix. This case will have matrix size [num_pic, num_pic]
    # which can be much smaller than standard approach where cov matrix will be [features, features]
    cov = np.matmul(images.transpose(), images)

    # Compute Eigenvalue and Eigenvector
    eig_value, eig_vector_temp = np.linalg.eig(cov)

    # Find true eigenvector
    eig_vector = np.matmul(images, eig_vector_temp)  # Convert vector back since we do transpose of normal cov matrix

    # Sort eigenvalue and correspond eigenvector by descending
    index = eig_value.argsort()[::-1]
    eig_value = eig_value[index]
    eig_vector = eig_vector[:, index]

    if percent_eigen is not None:  # percent_eigen mode
        assert 0 < percent_eigen < 100, "percent_eigen need to be between 0 to 100"
        # Calculate amount of eigenfaces by select the minimum amount that has total eigenvalues higher than threshold
        sum_eigenvalue = np.sum(eig_value, dtype='float32')
        for i in range(1, num_pic):
            if np.sum(eig_value[0:i]) > percent_eigen * sum_eigenvalue / 100:
                num_eigen = i
                print("Using {} eigenfaces".format(num_eigen))
                break
    else:  # num_eigen mode
        if num_pic < num_eigen:
            num_eigen = num_pic
            print("Warning: Eigenfaces is limited to no more than the number of training images")

    # Fetch a selected number of eigenface and eigenvalue
    eigenface = eig_vector[:, 0:num_eigen]

    # Select only num_Eig vectors and normalize to size of 1
    # eigenface = eig_vector/eig_vector.sum(axis=0,keepdims=1)  # Unused

    # return optimal projection axis and average image for future use
    return eigenface, eig_value


def reconstruct_image(images, num_eigenface, mode, image_dim=[100, 100]):
    """
    Transform the eigenface into an image and display with openCV for visualization
    :param images           : ndarray of image or eigenface with dimension
    :param num_eigenface    : int, amount of eigenface to visualize
    :param mode             : string. Type of image of the following option. Case-insensitive.
                            :'eig' or 'eig_inv' for eigenface of size [features, num_eigenface]
                            :'eig_inv' will give the inverted image instead
                            :'normal_im' for vectorized image of size [features]
    """
    # Return eigenface into image
    # reconstruct_image(eigenface[0],0,'eig') or reconstruct_image(eig_value[0],0,'normal_im')
    mode = mode.lower()
    mode_option = ['eig', 'eig_inv', 'normal_im']
    assert mode in mode_option, "Mode need to be one of the following: {}".format(mode_option)
    if mode == "eig":
        eigen_image = np.reshape(images[:, num_eigenface], (image_dim[0], image_dim[1]))
        eigen_image = eigen_image - np.min(eigen_image)
        eigen_image = np.array(eigen_image / np.max(eigen_image) * 255, dtype=np.uint8)
    elif mode == "eig_inv":
        eigen_image = np.reshape(images[:, num_eigenface], (image_dim[0], image_dim[1]))
        eigen_image = -eigen_image
        eigen_image = eigen_image - np.matrix.min(eigen_image)
        eigen_image = np.array(eigen_image / np.max(eigen_image) * 255, dtype=np.uint8)
    elif mode == "normal_im":
        eigen_image = np.reshape(images, (image_dim[0], image_dim[1]))
        eigen_image = np.array(eigen_image, dtype=np.uint8)
    else:
        print("Error mode : 'E' or 'Av'")
    im = cv2.resize(eigen_image, (400, 400))
    cv2.imshow("Eigenface Image: " + str(num_eigenface), im)

    cv2.waitKey(0)
    # cv2.destroyAllWindows()
    return


# ----------------Main Code -----------------------------#
if __name__ == '__main__':
    tic = timeit.default_timer()

    # Parameters
    precent_eig_param = [90.0, 90.0, 90.0, 90.0]  # Minimum of percentage of eigenvalue
    num_eig_param = None  # Number of Eig
    num_Pic = 21  # Number of Pictures
    image_dir = './TrainingPicsAll'  # Training pictures path
    img_index = []
    # img_index = ['1008.jpg', '1011.jpg', '1014.jpg', '1015.jpg', '1022.jpg', '1025.jpg',
    #              '1027.jpg', '1028.jpg', '1031.jpg', '1032.jpg', '1033.jpg', '1117.jpg',
    #              '1118.jpg', '1123.jpg', '1126.jpg', '1129.jpg']
    PCA_Path = './debug/train_debug.npz'  # Path to save PCA

    # Importing image
    data = {'image_emotion': ['hap', 'sad', 'ang', 'sur'],
            'train_image': [], 'average_image': [],
            'eigenface': [], 'eigenvalue': []
            }

    for i, emo in enumerate(data['image_emotion']):
        train_image, im_avg = import_images(image_dir, emo, img_index)
        eigface, eigval = create_eigface(train_image, num_eigen=None, percent_eigen=precent_eig_param[i])
        data['train_image'].append(train_image)
        data['average_image'].append(im_avg)
        data['eigenface'].append(eigface)
        data['eigenvalue'].append(eigval)

    # Save to "PCATrain.npz"
    File = open(PCA_Path, 'w+')
    File.close()
    np.savez(PCA_Path,
             Eig0=data['eigenface'][0], ImAv0=data['average_image'][0],
             Eig1=data['eigenface'][1], ImAv1=data['average_image'][1],
             Eig2=data['eigenface'][2], ImAv2=data['average_image'][2],
             Eig3=data['eigenface'][3], ImAv3=data['average_image'][3])

    toc = timeit.default_timer()

    print("Total time spend for training is: {} seconds".format(toc - tic))
    print("Total images for training is {}, {}, {}, {} images (For each emotion)".format(
        np.shape(data['train_image'][0])[1], np.shape(data['train_image'][1])[1],
        np.shape(data['train_image'][2])[1], np.shape(data['train_image'][3])[1]))
    print("Image size is {} features".format(np.shape(data['train_image'][0])[0]))
    print("Number of optimal projection axis is:", np.shape(data['eigenface'][0])[1])

'''
# Perform the tranining
recognizer.train(images, np.array(labels))
i = 0


# Append the images with the extension .sad into image_paths
image_paths = [os.path.join(path, f) for f in os.listdir(path) if f.endswith('.sad')]
for image_path in image_paths:
    predict_image_pil = Image.open(image_path).convert('L')
    predict_image = np.array(predict_image_pil, 'uint8')
    faces = faceCascade.detectMultiScale(predict_image)
    for (x, y, w, h) in faces:
        i = i+1
        cropped = np.array(cv2.resize(predict_image[y: y + h, x: x + w],(150,150)),'uint8')
        nbr_predicted, conf = recognizer.predict(cropped)
        nbr_actual = int(os.path.split(image_path)[1].split(".")[0].replace("subject", ""))
        if nbr_actual == nbr_predicted:
            print "{} is Correctly Recognized with confidence {}".format(nbr_actual, conf)
        else:
            print "{} is Incorrect Recognized as {}".format(nbr_actual, nbr_predicted)
        cv2.imshow("Recognizing Face", cropped)
        cv2.waitKey(1000)
        
'''
