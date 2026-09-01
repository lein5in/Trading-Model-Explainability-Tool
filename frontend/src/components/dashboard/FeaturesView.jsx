import FeatureImportanceByRegime from './FeatureImportanceByRegime'

function FeaturesView({ analysisResult }) {
  const { shap } = analysisResult

  return (
    <div className="space-y-4">
      <h2 className="text-sm font-semibold text-neutral-300 uppercase tracking-wider mb-2">
        Feature Importance
      </h2>

      <div className="border border-neutral-800 rounded p-4">
        <FeatureImportanceByRegime
          regimeSegmentedImportance={shap?.regime_segmented_importance}
          featureNames={shap?.feature_names ?? []}
        />
      </div>
    </div>
  )
}

export default FeaturesView