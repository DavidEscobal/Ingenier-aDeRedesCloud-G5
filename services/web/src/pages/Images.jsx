import { useCallback, useEffect, useRef, useState } from 'react'
import { Api, uploadImage } from '../api.js'
import { formatDate } from '../components.jsx'

const NAME = /^[a-z0-9][a-z0-9._-]{0,62}$/
const MAX_MB = 1024

function suggestName(file) {
  return file.name.toLowerCase().replace(/\.(qcow2|img|raw)$/, '').replace(/[^a-z0-9._-]+/g, '-').replace(/^[^a-z0-9]+/, '').slice(0, 63)
}

function mb(bytes) {
  return bytes == null ? '—' : (bytes / 1024 / 1024).toFixed(bytes < 10 * 1024 * 1024 ? 1 : 0) + ' MB'
}

export default function Images({ user }) {
  const [images, setImages] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [file, setFile] = useState(null)
  const [name, setName] = useState('')
  const [format, setFormat] = useState('qcow2')
  const [description, setDescription] = useState('')
  const [progress, setProgress] = useState(null)
  const fileInput = useRef(null)
  const admin = user.role === 'admin'

  const load = useCallback(async () => {
    try {
      setImages(await Api.images())
      setError('')
    } catch (err) {
      setError(err.message)
    }
  }, [])
  useEffect(() => { load() }, [load])

  function pick(event) {
    const f = event.target.files?.[0]
    setNotice('')
    setError('')
    if (!f) return
    setFile(f)
    setName(suggestName(f))
    // El formato se detecta por contenido (cabecera qcow2 "QFI\xfb"), no por la extensión: CirrOS publica qcow2 como .img.
    f.slice(0, 4).arrayBuffer()
      .then((buf) => {
        const b = new Uint8Array(buf)
        setFormat(b[0] === 0x51 && b[1] === 0x46 && b[2] === 0x49 && b[3] === 0xfb ? 'qcow2' : 'raw')
      })
      .catch(() => setFormat('qcow2'))
  }

  async function submit(event) {
    event.preventDefault()
    if (!file) return setError('Elige un archivo de imagen.')
    if (!NAME.test(name)) return setError('Nombre: minúsculas, números, punto, guion o guion bajo (máx. 63).')
    if (file.size > MAX_MB * 1024 * 1024) return setError(`La imagen supera ${MAX_MB} MB.`)
    if (images?.some((i) => i.name === name)) return setError('Ya existe una imagen con ese nombre.')
    setError('')
    setProgress(0)
    try {
      const image = await uploadImage(file, { name, disk_format: format, description }, setProgress)
      setNotice(`Imagen «${image.name}» importada (${mb(image.size)}, SHA-256 ${image.sha256.slice(0, 12)}…). Ya se puede usar en el editor.`)
      setFile(null)
      setName('')
      setDescription('')
      if (fileInput.current) fileInput.current.value = ''
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setProgress(null)
    }
  }

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>Imágenes</h1>
          <p className="sub">Imágenes disponibles para las VMs. Se guardan en el proveedor (hoy Glance de OpenStack);
            el catálogo de G5 registra sus metadatos.</p>
        </div>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      {notice && <p className="notice">{notice}</p>}

      {admin && (
        <form className="panel upload" onSubmit={submit} noValidate>
          <h2>Importar imagen</h2>
          <div className="upload-grid">
            <label>Archivo (.qcow2 o .img/.raw, hasta {MAX_MB} MB)
              <input ref={fileInput} type="file" accept=".qcow2,.img,.raw,application/octet-stream" onChange={pick} disabled={progress !== null} />
            </label>
            <label>Nombre<input value={name} onChange={(e) => setName(e.target.value.toLowerCase())} disabled={progress !== null} /></label>
            <label>Formato (detectado)
              <select value={format} onChange={(e) => setFormat(e.target.value)} disabled={progress !== null}>
                <option value="qcow2">qcow2</option><option value="raw">raw</option>
              </select>
            </label>
            <label>Descripción<input value={description} maxLength={200} onChange={(e) => setDescription(e.target.value)} disabled={progress !== null} /></label>
          </div>
          {file && <p className="muted small">{file.name} · {mb(file.size)}</p>}
          {progress !== null && (
            <div className="progress-bar" role="progressbar" aria-valuenow={progress} aria-valuemin="0" aria-valuemax="100">
              <div style={{ width: progress + '%' }} /><span>{progress < 100 ? `Subiendo… ${progress}%` : 'Registrando en Glance…'}</span>
            </div>
          )}
          <button type="submit" disabled={!file || progress !== null}>Importar</button>
        </form>
      )}

      <h2>Catálogo</h2>
      {images === null && !error && <p className="muted">Cargando…</p>}
      {images?.length > 0 && (
        <table className="table">
          <thead><tr><th>Nombre</th><th>Formato</th><th>Tamaño</th><th>Proveedor</th><th>Origen</th><th>Importada por</th><th>Fecha</th></tr></thead>
          <tbody>
            {images.map((i) => (
              <tr key={i.name}>
                <td><strong>{i.name}</strong>{i.description && <div className="muted small">{i.description}</div>}
                  {i.sha256 && <div className="mono small" title={i.sha256}>sha256 {i.sha256.slice(0, 16)}…</div>}</td>
                <td>{i.disk_format}</td>
                <td>{mb(i.size)}</td>
                <td><span className="provider provider-openstack">OpenStack</span></td>
                <td>{i.source === 'catalog' ? 'Catálogo G5' : 'Preexistente en Glance'}</td>
                <td>{i.uploaded_by || '—'}</td>
                <td>{typeof i.created_at === 'number' ? formatDate(i.created_at) : (i.created_at || '').slice(0, 10)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
