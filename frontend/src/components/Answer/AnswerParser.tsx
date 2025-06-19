import { cloneDeep } from 'lodash'

import { AskResponse, Citation } from '../../api'

export type ParsedAnswer = {
  citations: Citation[]
  markdownFormatText: string,
  generated_chart: string | null
} | null

export const enumerateCitations = (citations: Citation[]) => {
  const filepathMap = new Map()
  for (const citation of citations) {
    const { filepath } = citation
    let part_i = 1
    if (filepathMap.has(filepath)) {
      part_i = filepathMap.get(filepath) + 1
    }
    filepathMap.set(filepath, part_i)
    citation.part_index = part_i
  }
  return citations
}

export function parseAnswer(answer: AskResponse): ParsedAnswer {
  if (typeof answer.answer !== "string") return null
  let answerText = answer.answer

  // Match both single citations [doc1] and multiple citations [doc1, doc2, doc3]
  // Flexible regex to capture any citation pattern containing doc followed by numbers
  const citationLinks = answerText.match(/\[[^\]]*doc\d+[^\]]*\]/g)

  const lengthDocN = '[doc'.length

  let filteredCitations = [] as Citation[]
  let citationReindex = 0
  citationLinks?.forEach(link => {
    // Extract all doc numbers from the link using regex
    // This handles both [doc1] and [doc1, doc2, doc3] formats
    const docMatches = link.match(/doc(\d+)/g)
    
    if (!docMatches) {
      return
    }
    
    let replacementText = ''
    docMatches.forEach(docMatch => {
      // Extract just the number from "doc1", "doc2", etc.
      const docNumber = docMatch.replace('doc', '')
      const citationArrayIndex = Number(docNumber) - 1
      
      // Check if citation exists in the available citations array
      if (citationArrayIndex >= 0 && citationArrayIndex < answer.citations.length) {
        const citation = cloneDeep(answer.citations[citationArrayIndex]) as Citation
        
        if (!filteredCitations.find(c => c.id === docNumber) && citation) {
          if (replacementText) replacementText += ' '
          replacementText += ` ^${++citationReindex}^ `
          citation.id = docNumber // original doc index to de-dupe
          citation.reindex_id = citationReindex.toString() // reindex from 1 for display
          filteredCitations.push(citation)
        } else if (citation) {
          // Citation already exists, find its reindex
          const existingCitation = filteredCitations.find(c => c.id === docNumber)
          if (existingCitation) {
            if (replacementText) replacementText += ' '
            replacementText += ` ^${existingCitation.reindex_id}^ `
          }
        }
      }
    })
    
    // Replace the original citation link with numbered references
    answerText = answerText.replaceAll(link, replacementText)
  })

  filteredCitations = enumerateCitations(filteredCitations)

  /* Remplacement des liens pour ouvrir les documents */
  const matchesIdDocs = answerText.matchAll(/\[iddoc\|([^|]+)\|([^|]+)\]/g);

  for (const matchIdDoc of matchesIdDocs) {
      const idDuDoc = matchIdDoc[1]; // Premier groupe capturé (ID_DU_DOC)
      const refDuDoc = matchIdDoc[2]; // Deuxième groupe capturé (REF_DU_DOC)

      // Action personnalisée
      answerText = answerText.replaceAll(
          `[iddoc|${idDuDoc}|${refDuDoc}]`,
          `<span class="iddoc-link" data-id="${idDuDoc}" data-ref="${refDuDoc}">${refDuDoc}</span>`
      );
  }

  /* Remplacement des chaînes pour créer un enregistrement */
  const matchesCreateRecords = answerText.matchAll(/\[createRecord\|([^|]+)\|([^|]+)\]/g);

  for (const matchCreateRecord of matchesCreateRecords) {
      const titreLien = matchCreateRecord[1];
      const description = matchCreateRecord[2];
      // Action personnalisée
      answerText = answerText.replaceAll(
          `[createRecord|${titreLien}|${description}]`,
          `<span class="create-record-link" data-title="${titreLien}" data-description="${description}">${titreLien}</span>`
      );
  }

  return {
    citations: filteredCitations,
    markdownFormatText: answerText,
    generated_chart: answer.generated_chart
  }
}
