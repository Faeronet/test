// Package kafka holds the topic catalogue, the canonical event envelope, and
// the producer/consumer wrappers used by the API and Go workers. Python
// services share the same envelope via services-python/common.
package kafka

const (
	TopicFileUploaded               = "file.uploaded"
	TopicArchiveExtracted           = "archive.extracted"
	TopicPageExtracted              = "page.extracted"
	TopicPagePreprocessed           = "page.preprocessed"
	TopicPageRouted                 = "page.routed"
	TopicPageDiscardedSpecification = "page.discarded_specification"
	TopicPageSegmentationRequested  = "page.segmentation.requested"
	TopicPageSegmentationDone       = "page.segmentation.done"
	TopicPageOCRRequested           = "page.ocr.requested"
	TopicPageOCRDone                = "page.ocr.done"
	TopicPageGeometryRequested      = "page.geometry.requested"
	TopicPageGeometryDone           = "page.geometry.done"
	TopicPageQARequested            = "page.qa.requested"
	TopicPageQADone                 = "page.qa.done"
	TopicPageReviewRequired         = "page.review.required"
	TopicPageReviewAccepted         = "page.review.accepted"
	TopicPageExportRequested        = "page.export.requested"
	TopicPageExportDone             = "page.export.done"
	TopicPageFailed                 = "page.failed"
	TopicDeadletter                 = "deadletter"
)

// AllTopics is the canonical topic list, used for auto-creation in dev.
var AllTopics = []string{
	TopicFileUploaded,
	TopicArchiveExtracted,
	TopicPageExtracted,
	TopicPagePreprocessed,
	TopicPageRouted,
	TopicPageDiscardedSpecification,
	TopicPageSegmentationRequested,
	TopicPageSegmentationDone,
	TopicPageOCRRequested,
	TopicPageOCRDone,
	TopicPageGeometryRequested,
	TopicPageGeometryDone,
	TopicPageQARequested,
	TopicPageQADone,
	TopicPageReviewRequired,
	TopicPageReviewAccepted,
	TopicPageExportRequested,
	TopicPageExportDone,
	TopicPageFailed,
	TopicDeadletter,
}
