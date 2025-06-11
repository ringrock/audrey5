export const resizeImage = (file: Blob, maxWidth: number, maxHeight: number, quality: number = 0.8, useHighQuality: boolean = false): Promise<string> => {
  return new Promise((resolve, reject) => {
    const img = new Image()
    const reader = new FileReader()

    reader.readAsDataURL(file)
    reader.onloadend = () => {
      img.src = reader.result as string
      img.onload = () => {
        const canvas = document.createElement('canvas')
        const ctx = canvas.getContext('2d')

        let { width, height } = img

        // Calculate the new dimensions - only resize if necessary
        const needsResize = width > maxWidth || height > maxHeight
        if (needsResize) {
          if (width > height) {
            height = (maxWidth / width) * height
            width = maxWidth
          } else {
            width = (maxHeight / height) * width
            height = maxHeight
          }
          console.log(`Image resized from original to ${Math.round(width)}x${Math.round(height)}`)
        } else {
          console.log(`Image kept at original size: ${width}x${height}`)
        }

        canvas.width = width
        canvas.height = height

        if (ctx) {
          ctx.drawImage(img, 0, 0, width, height)
        }

        // Convert the canvas to a base64 string with optimal format
        const resizedBase64 = useHighQuality && (width * height) < 1000000 ? 
          canvas.toDataURL('image/png') :  // PNG sans perte pour petites images
          canvas.toDataURL('image/jpeg', quality)
        resolve(resizedBase64)
      }

      img.onerror = error => {
        reject('Error loading image: ' + error)
      }
    }

    reader.onerror = error => {
      reject('Error reading file: ' + error)
    }
  })
}
