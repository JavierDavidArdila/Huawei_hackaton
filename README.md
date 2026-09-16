# maas-hackathon-260526

Repositorio oficial para recopilar las soluciones y retos desarrollados por los participantes del Hackatón Huawei Colombia MaaS

---

# Guía de Entrega de Retos

Con el objetivo de mantener el repositorio organizado y facilitar el proceso de revisión y evaluación, todos los participantes deben seguir cuidadosamente las siguientes instrucciones para realizar la entrega de sus soluciones.

---

# Fecha límite de entrega

> **IMPORTANTE**  
> Las soluciones podrán enviarse únicamente hasta las **DEFINIR HORA LIMITE**.  
> Después de esa hora, **no se permitirán más commits, pushes ni Pull Requests al repositorio**.

Se recomienda realizar la entrega con anticipación para evitar inconvenientes técnicos de última hora.

---

## 1. Clonar el repositorio

Clona el repositorio oficial en tu máquina local:

```bash
git clone https://github.com/huawei-cloud-colombia/Huawei_hackaton.git
cd Huawei_hackaton
```

---

## 2. Crear una rama propia

Antes de realizar cualquier modificación, crea una rama independiente utilizando tu primer nombre, primer apellido en minúsculas y G-numero de grupo, separados por un guion (`-`) y sin caracteres especiales (sin tildes ni `ñ`).

### Ejemplo

```text
Juan Rodríguez Grupo 1 → juan-rodriguez-g1
```

### Crear la rama

```bash
git checkout -b tu-nombre-apellido-g#grupo
```

---

## 3. Crear la estructura del proyecto

Dentro de tu rama, debes crear una carpeta en la raíz del repositorio utilizando exactamente el mismo nombre de tu rama.

La estructura del proyecto debe verse de la siguiente manera:

```text
📂 tu-nombre-apellido-g#grupo/
├── 📄 README.md              # Instrucciones claras para ejecutar el proyecto
├── 📄 requerimientos.txt     # Dependencias y librerías necesarias
├── 📄 prompt_usado.txt       # Prompts utilizados en Huawei MaaS
└── 📂 codigo/                # Código fuente del desarrollo
```

---

## Archivos requeridos

| Archivo | Descripción |
|---|---|
| `README.md` | Explica claramente cómo instalar, configurar y ejecutar el proyecto. |
| `requerimientos.txt` | Lista de dependencias necesarias para ejecutar la solución. |
| `prompt_usado.txt` | Debe incluir los prompts utilizados durante el desarrollo en Huawei MaaS. |
| `codigo/` | Carpeta que contiene el código fuente completo del proyecto. |

---

## 4. Guardar y subir los cambios

Una vez tengas lista tu estructura y archivos, guarda los cambios, crea un commit y sube únicamente tu rama al repositorio remoto.

```bash
git add tu-nombre-apellido-g#grupo/
git commit -m "feat: entrega de reto X de Tu Nombre"
git push origin tu-nombre-apellido-g#grupo
```

---

# Notas importantes

## Seguridad

Está estrictamente prohibido subir:

- Archivos `.env`
- Credenciales
- Tokens
- Claves privadas
- Información sensible o confidencial

Asegúrate de incluir estos archivos y directorios en tu `.gitignore`.

---

# Recomendación: crear un `.gitignore`

Se recomienda crear un archivo `.gitignore` desde el inicio del desarrollo para evitar subir archivos innecesarios o sensibles.

## Ejemplo básico de `.gitignore`

```gitignore
# Variables de entorno
.env
*.env

# Entornos virtuales
.venv/
venv/

# Caché de Python
__pycache__/

# Archivos del sistema
.DS_Store
```

---

# Resumen rápido del flujo de trabajo

```bash
# 1. Clonar repositorio
git clone https://github.com/huawei-cloud-colombia/Huawei_hackaton.git

# 2. Entrar al proyecto
cd Huawei_hackaton

# 3. Crear rama personal
git checkout -b tu-nombre-apellido-g#grupo

# 4. Crear estructura del proyecto
# (Agregar carpeta y archivos requeridos)

# 5. Guardar cambios
git add tu-nombre-apellido-g#/

# 6. Crear commit
git commit -m "feat: entrega de reto de Tu Nombre y grupo"

# 7. Subir rama
git push origin tu-nombre-apellido-g#

```

---

Muchas gracias por participar y ¡éxitos en el desarrollo del reto!
