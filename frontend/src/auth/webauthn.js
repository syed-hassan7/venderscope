/** WebAuthn helpers — base64url encode/decode for browser credentials API */

function bufferToBase64url(buffer) {
  const bytes = new Uint8Array(buffer)
  let str = ''
  for (const b of bytes) str += String.fromCharCode(b)
  return btoa(str).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '')
}

function base64urlToBuffer(base64url) {
  const padded = base64url.replace(/-/g, '+').replace(/_/g, '/')
  const pad = padded.length % 4 === 0 ? '' : '='.repeat(4 - (padded.length % 4))
  const binary = atob(padded + pad)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return bytes.buffer
}

function decodeCreationOptions(serverOptions) {
  const { challengeId, userId, ...rest } = serverOptions
  const publicKey = { ...rest }
  if (publicKey.challenge) publicKey.challenge = base64urlToBuffer(publicKey.challenge)
  if (publicKey.user?.id) publicKey.user.id = base64urlToBuffer(publicKey.user.id)
  if (publicKey.excludeCredentials) {
    publicKey.excludeCredentials = publicKey.excludeCredentials.map((c) => ({
      ...c,
      id: base64urlToBuffer(c.id),
    }))
  }
  return { challengeId, userId, publicKey }
}

function decodeRequestOptions(serverOptions) {
  const { challengeId, ...rest } = serverOptions
  const publicKey = { ...rest }
  if (publicKey.challenge) publicKey.challenge = base64urlToBuffer(publicKey.challenge)
  if (publicKey.allowCredentials) {
    publicKey.allowCredentials = publicKey.allowCredentials.map((c) => ({
      ...c,
      id: base64urlToBuffer(c.id),
    }))
  }
  return { challengeId, publicKey }
}

function credentialToJSON(credential) {
  const response = credential.response
  const out = {
    id: credential.id,
    rawId: bufferToBase64url(credential.rawId),
    type: credential.type,
    response: {
      clientDataJSON: bufferToBase64url(response.clientDataJSON),
    },
  }
  if (response.attestationObject) {
    out.response.attestationObject = bufferToBase64url(response.attestationObject)
  }
  if (response.authenticatorData) {
    out.response.authenticatorData = bufferToBase64url(response.authenticatorData)
  }
  if (response.signature) {
    out.response.signature = bufferToBase64url(response.signature)
  }
  if (response.getTransports) {
    out.response.transports = response.getTransports()
  }
  return out
}

export async function createPasskey(serverOptions) {
  const { challengeId, publicKey } = decodeCreationOptions(serverOptions)
  const credential = await navigator.credentials.create({ publicKey })
  if (!credential) throw new Error('Passkey creation was cancelled')
  return { challenge_id: challengeId, credential: credentialToJSON(credential) }
}

export async function getPasskeyAssertion(serverOptions) {
  const { challengeId, publicKey } = decodeRequestOptions(serverOptions)
  const credential = await navigator.credentials.get({ publicKey })
  if (!credential) throw new Error('Passkey sign-in was cancelled')
  return { challenge_id: challengeId, credential: credentialToJSON(credential) }
}

export function isWebAuthnSupported() {
  return typeof window !== 'undefined' && window.PublicKeyCredential != null
}
